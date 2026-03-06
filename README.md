# Class Fund Manager

A multi-tenant Django web application for managing school class funds.
Treasurers collect money, track expenses, and give students and parents
full transparency into where the class fund stands.

---

## Homework for 5. Mar. 2026

### Technical overview

The project is a focused solution for school-level financial governance, designed around clear separation of concerns and strict multi‑tenancy. It models the lifecycle of a classroom payment: creation, collection, reconciliation and spending. Core domain artifacts include the <u>PaymentRequest</u> issued by a treasurer, the recorded <u>Transaction</u> representing an incoming payment, and the logged <u>Expense</u> representing money leaving the fund. Each class has a linked <u>BankAccount</u> and a computed <u>Fund Balance</u> derived from confirmed transactions minus published expenses.

Identity and authorization are central. Roles consist of an unauthenticated visitor, a <u>Student</u>, a <u>Parent</u>, and elevated operators: the <u>System Admin</u> and tiered <u>Treasurer</u> roles. Treasurers are scoped to a <u>SchoolClass</u> via a <u>ClassMembership</u>, and per-class permissions are captured in named <u>FundGroup</u> entries so administrators can define who may log expenses, create payment requests, or view bank details. Students are represented by <u>StudentProfile</u> records and identified for bank reconciliation using a numeric <u>Variable Symbol (VS)</u>, generated deterministically per class.

Operational features include bulk provisioning via the <u>Importer</u> (CSV import), on‑screen editable previews, and QR generation using the <u>SPAYD QR</u> format to simplify payer UX. The reconciliation pipeline anticipates automatic matching against incoming transfers fetched from the <u>Fio Bank API</u>, with unmatched items held for manual review.

The architecture enforces the non‑negotiable rule: never query scoped financial entities without filtering by <u>SchoolClass</u>, ensuring strict tenant isolation. This design, combined with explicit auditing of imports and notifications, provides a traceable, role-aware system tailored to the practical workflows of teachers, parents and administrators managing class funds.

### User-flow

![User flow](./user-flow.drawio.svg)
[User flow](./user-flow.drawio.svg)



### Wireframe

![Wireframe](./Wireframe.drawio.svg)
[Wireframe](./Wireframe.drawio.svg)

---

## Quick start (local development)

### Prerequisites

- Python 3.13+
- Git

### 1. Clone & enter the repo

```bash
git clone https://github.com/gyarab/2025_wt_prj_dembinny.git
cd 2025_wt_prj_dembinny
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv

# Windows (bash / Git Bash)
source .venv/Scripts/activate

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

**`requirements.txt` installs:**
`django`, `qrcode[pil]`, `Pillow`, `gunicorn`, `whitenoise`, `dj-database-url`,
`psycopg2-binary`, `python-dotenv`, `django-extensions`

### 4. Configure environment variables

Create a `.env` file in the **repository root** (`2025_wt_prj_dembinny/.env`).
The app uses `python-dotenv` and loads it automatically on startup.

```env
# Required
SECRET_KEY=your-long-random-secret-key-here

# Optional — defaults shown
DEBUG=True
ALLOWED_HOSTS=*

# Database — leave blank to use local SQLite (default for development)
# DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

A complete template is in `.env.example`.

### 5. Run database migrations

```bash
cd prj
python manage.py migrate
```

### 6. Create the first System Admin account

```bash
python manage.py createsuperuser
```

Log in at `/admin/` and set the user's `role` to `SYSTEM_ADMIN`, or use the
app's native login at `/login/`.

### 7. Start the development server

```bash
python manage.py runserver
```

Open `http://127.0.0.1:8000/` — unauthenticated users see the landing page.

---

## Project layout

```
2025_wt_prj_dembinny/
├── .env                    ← local secrets (git-ignored)
├── .env.example            ← template for new developers
├── requirements.txt
├── runtime.txt             ← python-3.13.5 (Render reads this automatically)
├── AI_CONTEXT.md           ← master AI navigation manual
├── FINANCE_LOGIC.md        ← business logic & financial documentation
├── PARENT_FAQ.md           ← end-user FAQ for parents
├── TEACHER_MANUAL.tex      ← LaTeX teacher/treasurer manual
└── prj/                    ← Django project root
    ├── manage.py
    ├── db.sqlite3          ← local SQLite (git-ignored in production)
    ├── prj/                ← settings, root urls, wsgi, asgi
    ├── accounts/           ← users, roles, classes, VS generation
    ├── core/               ← public pages, base templates, context processor
    ├── finances/           ← payments, transactions, expenses, QR codes
    ├── communications/     ← outbound email log
    └── importer/           ← CSV bulk student import
```

---

## Environment variables reference

| Variable             | Default             | Prod required?        | Description                                     |
| -------------------- | ------------------- | --------------------- | ----------------------------------------------- |
| `SECRET_KEY`         | insecure dev key    | **Yes**               | Django cryptographic signing key                |
| `DEBUG`              | `True`              | **Yes** — set `False` | Disables error pages in production              |
| `ALLOWED_HOSTS`      | `*`                 | **Yes**               | Comma-separated hostnames                       |
| `DATABASE_URL`       | *(SQLite fallback)* | **Yes**               | Full PostgreSQL connection string               |
| `DEFAULT_FROM_EMAIL` | *(unset)*           | Yes (email features)  | Sender address for notifications                |
| `SITE_URL`           | *(unset)*           | Yes (email features)  | Base URL for links inside emails                |
| `CUSTOM_DATABASE`    | *(unset)*           | Alternative           | Set to `postgresql` to use separate `DB_*` vars |

When `CUSTOM_DATABASE=postgresql`, also provide: `DB_NAME`, `DB_USER`, `PASSWORD`, `DB_HOST`, `DB_PORT`.

---

## Production deployment (Render + Supabase)

### Architecture

```
GitHub (main branch)
      ↓  automatic deploy on every push
Render Web Service  (Python 3.13, Gunicorn)
      ↓  DATABASE_URL  (SSL, IPv4 Pooler)
Supabase PostgreSQL
```

### Render web service settings

| Setting           | Value                                                                                                               |
| ----------------- | ------------------------------------------------------------------------------------------------------------------- |
| **Build command** | `pip install -r requirements.txt && cd prj && python manage.py collectstatic --noinput && python manage.py migrate` |
| **Start command** | `cd prj && gunicorn prj.wsgi:application`                                                                           |
| **Runtime**       | Render auto-detects from `runtime.txt` → `python-3.13.5`                                                            |

### Required Render environment variables

```
SECRET_KEY         = <generate: python -c "import secrets; print(secrets.token_urlsafe(50))">
DEBUG              = False
ALLOWED_HOSTS      = two025-wt-prj-dembinny.onrender.com
DATABASE_URL       = <Supabase IPv4 Pooler URL>
DEFAULT_FROM_EMAIL = noreply@yourdomain.cz
SITE_URL           = https://two025-wt-prj-dembinny.onrender.com
```

### Getting the Supabase DATABASE_URL

1. Supabase dashboard → **Project Settings → Database**
2. **Connection string → URI tab**
3. Select **Session Pooler (IPv4)** — required because Render uses IPv4
4. Copy and paste into Render as `DATABASE_URL`

Format: `postgresql://postgres.[ref]:[password]@aws-0-eu-central-1.pooler.supabase.com:5432/postgres`

### CSRF trusted origins

Hardcoded in `prj/settings.py`:
```python
CSRF_TRUSTED_ORIGINS = ['https://two025-wt-prj-dembinny.onrender.com']
```
Add your custom domain here if you configure one on Render.

### Cron jobs (planned)

| Schedule       | Command                                             | Purpose                   |
| -------------- | --------------------------------------------------- | ------------------------- |
| `*/15 * * * *` | `cd prj && python manage.py fetch_fio_transactions` | Import Fio Bank transfers |
| `0 8 * * *`    | `cd prj && python manage.py send_payment_reminders` | Daily reminder emails     |

These management commands are not yet implemented. See `AI_CONTEXT.md` § 8.

---

## Running tests

```bash
cd prj
python manage.py test importer   # parser unit tests — no database required
python manage.py test            # full test suite
```

---

## Useful management commands

```bash
python manage.py migrate                     # apply migrations
python manage.py collectstatic --noinput     # production static files
python manage.py shell                       # interactive Django shell

# Entity-relationship diagram (requires graphviz installed)
python manage.py graph_models accounts finances communications importer \
    -o models_diagram.svg
```

---

## Technology stack

| Layer           | Technology                      |
| --------------- | ------------------------------- |
| Language        | Python 3.13.5                   |
| Framework       | Django 6.x                      |
| Database (dev)  | SQLite                          |
| Database (prod) | PostgreSQL via Supabase         |
| Web server      | Gunicorn                        |
| Static files    | WhiteNoise (CompressedManifest) |
| QR codes        | `qrcode[pil]` + Pillow          |
| Hosting 01      | Render.com                      |
| Hosting 02      | PythonAnywhere.com              |
| Hosting 03      | fund.svs.gyarab.cz              |
| Frontend        | Bootstrap 5 (CDN) + custom CSS  |

