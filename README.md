DreamLance — Local Development (Unified Server)

This project is a unified site combining a frontend and a Flask backend (`app.py`) to accept project/job requests, serve the project explorer, manage jobs & news feeds, and provide administrative/database dashboards on a single port.

Quick start (PowerShell):

```powershell
cd 'C:\Users\Kiran\Dreamlance'
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# optionally set env vars, e.g.:
# $env:ADMIN_USER='admin'; $env:ADMIN_PASS='secret'; $env:SMTP_HOST='smtp.example.com'; $env:SMTP_PORT='587'; $env:SMTP_USER='smtpuser'; $env:SMTP_PASS='smtppass'; $env:FROM_EMAIL='no-reply@example.com'
python app.py
```

Open http://localhost:8000 for the site and http://localhost:8000/admin for admin (login required; default admin/Kiran@1598 unless overridden by environment variables).

Environment variables
- `ADMIN_USER`, `ADMIN_PASS` — admin credentials for `/api/requests/list` and estimate endpoints. Defaults: `Kiran1598`/`Kiran@1598` (change in production).
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `FROM_EMAIL` — SMTP settings to send emails.
- `SENDGRID_API_KEY` — alternatively use SendGrid API to send emails.

Deployment
1. Initialize Git if needed:
   ```powershell
   git init
   git add .
   git commit -m "Initial DreamLance deployment setup"
   ```
2. Push to a platform such as Render, Railway, or Heroku.
3. Ensure environment variables are configured on the host, including `ADMIN_USER`, `ADMIN_PASS`, and email credentials.
4. On the host, the app will start with `gunicorn app:app`.

Recommended deployment steps for Render / Heroku
- Use `requirements.txt`, `Procfile`, and `runtime.txt`.
- Keep `.env` and `data.db` local only; do not commit them.
- For production, replace SQLite with a managed database and enable HTTPS.

Notes
- The backend stores requests in `data.db` (SQLite). For production, switch to a managed DB and add auth + HTTPS.
- The jobs feed is proxied from Remotive (`/api/jobs`).
