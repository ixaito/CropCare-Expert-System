import csv
import io
import json
from datetime import datetime
from typing import Annotated
from fastapi import Body, Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from email_validator import validate_email, EmailNotValidError

from .auth import (
    create_reset_token,
    current_user,
    find_valid_reset_token,
    hash_password,
    normalize_email,
    require_user,
    send_password_reset_email,
    verify_password,
)
from .config import settings
from .database import Base, engine, get_db
from .models import Consultation, User
from .rules import diagnose, load_questions, next_question

Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.app_name)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, same_site="lax", https_only=False)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


def render(request: Request, template_name: str, context: dict | None = None, status_code: int = 200):
    context = context or {}
    db_gen = get_db()
    db = next(db_gen)
    try:
        context["request"] = request
        context["app_name"] = settings.app_name
        context["user"] = current_user(request, db)
        return templates.TemplateResponse(
            request=request,
            name=template_name,
            context=context,
            status_code=status_code
        )
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return render(request, "landing.html")

    latest = (
        db.query(Consultation)
        .filter(Consultation.user_id == user.id)
        .order_by(Consultation.created_at.desc())
        .limit(5)
        .all()
    )
    return render(request, "dashboard.html", {"latest": latest})


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request):
    return render(request, "signup.html")


@app.post("/signup")
def signup(
    request: Request,
    full_name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    try:
        valid = validate_email(email, check_deliverability=False)
        email = normalize_email(valid.normalized)
    except EmailNotValidError as error:
        return render(request, "signup.html", {"error": str(error)}, status_code=400)

    if len(password) < 8:
        return render(request, "signup.html", {"error": "Password must be at least 8 characters."}, status_code=400)

    user = User(full_name=full_name.strip(), email=email, password_hash=hash_password(password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return render(request, "signup.html", {"error": "An account with this email already exists."}, status_code=400)

    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return render(request, "login.html")


@app.post("/login")
def login(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    email = normalize_email(email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return render(request, "login.html", {"error": "Invalid email or password."}, status_code=400)
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    return render(request, "forgot_password.html")


@app.post("/forgot-password")
def forgot_password(
    request: Request,
    email: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    email = normalize_email(email)
    user = db.query(User).filter(User.email == email).first()
    if user:
        raw_token = create_reset_token(db, user)
        reset_url = f"{settings.app_base_url}/reset-password/{raw_token}"
        send_password_reset_email(user.email, reset_url)

    return render(
        request,
        "forgot_password.html",
        {"success": "If the email exists, a password reset link has been sent. In development mode, check the terminal."},
    )


@app.get("/reset-password/{token}", response_class=HTMLResponse)
def reset_password_page(request: Request, token: str, db: Session = Depends(get_db)):
    reset_token = find_valid_reset_token(db, token)
    if not reset_token:
        return render(request, "reset_password.html", {"error": "Invalid or expired reset link.", "token": token}, status_code=400)
    return render(request, "reset_password.html", {"token": token})


@app.post("/reset-password/{token}")
def reset_password(
    request: Request,
    token: str,
    password: Annotated[str, Form()],
    db: Session = Depends(get_db),
):
    if len(password) < 8:
        return render(request, "reset_password.html", {"error": "Password must be at least 8 characters.", "token": token}, status_code=400)

    reset_token = find_valid_reset_token(db, token)
    if not reset_token:
        return render(request, "reset_password.html", {"error": "Invalid or expired reset link.", "token": token}, status_code=400)

    user = db.get(User, reset_token.user_id)
    user.password_hash = hash_password(password)
    reset_token.used = True
    db.commit()
    return render(request, "login.html", {"success": "Password updated. Please log in with your new password."})


@app.get("/diagnose", response_class=HTMLResponse)
def diagnose_page(request: Request, db: Session = Depends(get_db)):
    require_user(request, db)
    return render(request, "diagnose.html")


@app.get("/api/questions/start")
def start_questions(request: Request, db: Session = Depends(get_db)):
    require_user(request, db)
    questions = load_questions()
    return {"question": questions[0] if questions else None}


@app.post("/api/questions/next")
def api_next_question(
    request: Request,
    answers: Annotated[dict, Body(embed=True)],
    db: Session = Depends(get_db),
):
    require_user(request, db)
    question = next_question(answers)
    return {"question": question, "is_complete": question is None}


@app.post("/api/diagnose")
def api_diagnose(
    request: Request,
    answers: Annotated[dict, Body(embed=True)],
    db: Session = Depends(get_db),
):
    user = require_user(request, db)
    if "crop_type" not in answers:
        return JSONResponse({"error": "Crop type is required."}, status_code=400)

    result = diagnose(answers)
    consultation = Consultation(
        user_id=user.id,
        crop_type=str(answers.get("crop_type", "Unknown")),
        answers_json=json.dumps(answers, ensure_ascii=False),
        diagnosis_json=json.dumps(result, ensure_ascii=False),
    )
    db.add(consultation)
    db.commit()
    db.refresh(consultation)

    return {"consultation_id": consultation.id, "result": result}


@app.get("/history", response_class=HTMLResponse)
def history(request: Request, db: Session = Depends(get_db)):
    user = require_user(request, db)
    consultations = (
        db.query(Consultation)
        .filter(Consultation.user_id == user.id)
        .order_by(Consultation.created_at.desc())
        .all()
    )
    return render(request, "history.html", {"consultations": consultations})


@app.get("/consultations/{consultation_id}", response_class=HTMLResponse)
def consultation_detail(request: Request, consultation_id: int, db: Session = Depends(get_db)):
    user = require_user(request, db)
    consultation = db.get(Consultation, consultation_id)
    if not consultation or consultation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Consultation not found")
    answers = json.loads(consultation.answers_json)
    result = json.loads(consultation.diagnosis_json)
    return render(request, "result_detail.html", {"consultation": consultation, "answers": answers, "result": result})


@app.get("/consultations/{consultation_id}/export.json")
def export_json(request: Request, consultation_id: int, db: Session = Depends(get_db)):
    user = require_user(request, db)
    consultation = db.get(Consultation, consultation_id)
    if not consultation or consultation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Consultation not found")

    payload = {
        "id": consultation.id,
        "crop_type": consultation.crop_type,
        "created_at": consultation.created_at.isoformat(),
        "answers": json.loads(consultation.answers_json),
        "diagnosis": json.loads(consultation.diagnosis_json),
    }
    return StreamingResponse(
        io.BytesIO(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=consultation_{consultation.id}.json"},
    )


@app.get("/consultations/{consultation_id}/export.csv")
def export_csv(request: Request, consultation_id: int, db: Session = Depends(get_db)):
    user = require_user(request, db)
    consultation = db.get(Consultation, consultation_id)
    if not consultation or consultation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Consultation not found")

    answers = json.loads(consultation.answers_json)
    diagnosis = json.loads(consultation.diagnosis_json)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Consultation ID", consultation.id])
    writer.writerow(["Date", consultation.created_at.isoformat()])
    writer.writerow(["Crop", consultation.crop_type])
    writer.writerow([])
    writer.writerow(["Diagnosis", diagnosis.get("decision")])
    writer.writerow(["Confidence", f"{diagnosis.get('confidence', 0)}%"])
    writer.writerow(["Summary", diagnosis.get("summary")])
    writer.writerow(["Recommendation", diagnosis.get("recommendation")])
    writer.writerow(["Expert Note", diagnosis.get("expert_note")])
    writer.writerow([])
    writer.writerow(["Question/Field", "Answer"])
    for key, value in answers.items():
        writer.writerow([key, value])

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=consultation_{consultation.id}.csv"},
    )
