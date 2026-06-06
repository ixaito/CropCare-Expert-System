import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import smtplib
import bcrypt
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session
from .config import settings
from .models import User, PasswordResetToken


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def normalize_email(email: str) -> str:
    return email.strip().lower()


def current_user(request: Request, db: Session) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, int(user_id))


def require_user(request: Request, db: Session) -> User:
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/login"})
    return user


def create_reset_token(db: Session, user: User) -> str:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
    )
    db.add(reset_token)
    db.commit()
    return raw_token


def find_valid_reset_token(db: Session, raw_token: str) -> PasswordResetToken | None:
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.used == False,  # noqa: E712
    ).first()
    if not reset_token:
        return None
    expires_at = reset_token.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    return reset_token


def send_password_reset_email(to_email: str, reset_url: str) -> None:
    subject = "Password reset for Crop Disease Diagnostic System"
    body = (
        "Hello,\n\n"
        "A password reset was requested for your account.\n"
        f"Reset your password using this link: {reset_url}\n\n"
        "This link expires in 30 minutes. If you did not request this, ignore this email.\n"
    )

    if not settings.smtp_host or not settings.smtp_user or not settings.smtp_password:
        print("\n[DEV PASSWORD RESET LINK]")
        print(reset_url)
        print("[END DEV PASSWORD RESET LINK]\n")
        return

    message = EmailMessage()
    message["From"] = settings.smtp_from
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        if settings.smtp_tls:
            server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)


def safe_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
