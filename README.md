# Agricultural Crop Disease Diagnostic System

A small-scale rule-based expert system prototype for WIA3005 / WIE3005 Knowledge Management & Engineering.

## Features

- User signup, login, logout
- Forgot password and password reset token flow
- Rule-based crop disease diagnosis
- Adaptive questionnaire
- Saved consultation history
- View past results
- Export result as JSON or CSV
- `.env` based configuration

## Setup

```bash
python -m venv .venv
```

Windows PowerShell:

```bash
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create environment file:

```bash
copy .env.example .env
```

On macOS/Linux:

```bash
cp .env.example .env
```

Run:

```bash
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

## Notes for demo

If SMTP credentials are not configured, password reset links are printed in the terminal. This is suitable for assignment demonstration. For real deployment, configure SMTP settings in `.env`.

## Project structure

```text
agri_disease_expert_system/
├── app/
│   ├── data/
│   │   ├── questions.json
│   │   └── rules.json
│   ├── static/
│   │   ├── app.js
│   │   └── style.css
│   ├── templates/
│   │   ├── base.html
│   │   ├── dashboard.html
│   │   ├── diagnose.html
│   │   ├── forgot_password.html
│   │   ├── history.html
│   │   ├── landing.html
│   │   ├── login.html
│   │   ├── reset_password.html
│   │   ├── result_detail.html
│   │   └── signup.html
│   ├── auth.py
│   ├── config.py
│   ├── database.py
│   ├── main.py
│   ├── models.py
│   └── rules.py
├── .env.example
├── README.md
└── requirements.txt
```
