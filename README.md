# PerfectCRM

O'quv markaz uchun platforma: o'quvchilar, guruhlar, jadval, davomat (Telegram bot), to'lovlar, chek, SMS (Eskiz.uz), hisobotlar.
Batafsil: [docs/TZ.md](docs/TZ.md).

## Tuzilma

- `backend/` — Django + DRF (API `/api/`), Telegram bot, Eskiz SMS
- `frontend/` — React + TypeScript + Ant Design (admin paneli)

## Ishga tushirish (kompyuterda)

```bash
# 1) Backend
cd backend
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser   # admin: telefon + parol
.venv\Scripts\python.exe manage.py runserver

# 2) Frontend (boshqa terminalda)
cd frontend
npm run dev            # http://localhost:5173

# 3) Telegram bot + xabarlar navbati (boshqa terminalda)
cd backend
.venv\Scripts\python.exe manage.py run_bot

# Kunlik vazifalar (serverda cron orqali har kuni ertalab)
.venv\Scripts\python.exe manage.py daily_jobs
```

## Demo ma'lumotlar bilan sinash

Alohida `demo.sqlite3` bazasida (asosiy baza o'zgarmaydi):

```bash
cd backend
set SQLITE_NAME=demo.sqlite3
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py seed_demo
.venv\Scripts\python.exe manage.py runserver
```

Kirish: `+998900000000`, parol — `backend/.env` dagi `DEV_ADMIN_PASSWORD`.

## Testlar

```bash
cd backend
.venv\Scripts\python.exe manage.py test apps
```
