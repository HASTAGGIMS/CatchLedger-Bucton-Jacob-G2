# CatchLedger

**A Catch Recording and Sales Management System for a Fishermen's Cooperative**

Full-stack Django (templates + Bootstrap 5) with PostgreSQL / Supabase.
This repository currently contains **Phase 1: the Account feature**, which every later module depends on.

## Phase 1 - Account feature

| Requirement | Where |
|---|---|
| Registration with validation (required fields, email format, unique username **and** email, password confirmation) | `accounts/forms.py` (`RegistrationForm`), `accounts/views.py` (`register`) |
| Passwords hashed with Django's built-in auth (PBKDF2-SHA256) | `AUTH_USER_MODEL = accounts.User`, never stored in plain text |
| Login / logout with messages; invalid credentials show an error | `CatchLedgerLoginView`, `CatchLedgerLogoutView` (logout is POST-only) |
| Protected pages -> redirect to login | `@login_required` / `@role_required` in `accounts/decorators.py` |
| Role-based dashboards (Recorder, Cashier, Manager) | `dashboard_recorder`, `dashboard_cashier`, `dashboard_manager` |
| A user cannot open another role's dashboard by URL | `@role_required` returns **403 Access denied** |
| Profile: view and update own details (name, email, contact number, photo) | `/accounts/profile/`, `/accounts/profile/edit/` - no user id in the URL, so only your own profile is reachable |
| Change password | `/accounts/password/change/` |
| Manager user management (change role, deactivate) | `/accounts/manage/users/` (Manager only) |

### Roles (from the SDD)

| Role | Dashboard | Notes |
|---|---|---|
| **Recorder** | `/accounts/dashboard/recorder/` | Landing-site encoder |
| **Cashier** | `/accounts/dashboard/cashier/` | Sales, payments, advances, payouts |
| **Manager** | `/accounts/dashboard/manager/` | Also manages users |

* After login, `/accounts/dashboard/` sends each user to the dashboard for their role.
* **Registration** offers *Recorder* or *Cashier* only. The **Manager** role can never be self-assigned (SDD rule BR-03): it is given by an existing Manager on the *Manage users* page, or by `createsuperuser` for the first Manager.
* A Manager cannot demote or deactivate their own account (prevents lock-out).

## Setup

Requirements: Python 3.11+ and a PostgreSQL database (local or Supabase).

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd <your-repo-folder>

# 2. Virtual environment + dependencies
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure the environment
cp .env.example .env              # Windows: copy .env.example .env
#    then edit .env: DJANGO_SECRET_KEY and DATABASE_URL

# 4. Create the database tables
python manage.py migrate

# 5. Create the first Manager (superuser accounts get the Manager role)
python manage.py createsuperuser

#    ...or create one demo account per role for testing (DEBUG only):
python manage.py seed_demo_users   # demo_manager / demo_cashier / demo_recorder

# 6. Run
python manage.py runserver
```

Open <http://127.0.0.1:8000/>.

### Local PostgreSQL

```sql
CREATE USER catchledger WITH PASSWORD 'your_password' CREATEDB;
CREATE DATABASE catchledger OWNER catchledger;
```

`.env`: `DATABASE_URL=postgres://catchledger:your_password@localhost:5432/catchledger`

### Supabase

Supabase is PostgreSQL. In the dashboard open *Project Settings -> Database -> Connection string (URI)* and put it in `.env`:

```
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
DATABASE_SSLMODE=require
```

The project **refuses to start without `DATABASE_URL`** and rejects non-PostgreSQL URLs: there is no SQLite fallback.

## Tests

```bash
python manage.py test accounts
```

42 tests cover registration validation, password hashing, login/logout, protected pages, role isolation, user management and the profile (including photo upload). They run against PostgreSQL; the database user needs the `CREATEDB` privilege so Django can create `test_<name>`.

## Project structure

```
config/                 Django settings (env-driven), root URLs
accounts/               Account feature: User model, forms, views, tests
  management/commands/  seed_demo_users
templates/              base layout, partials, account pages, 403 page
static/css/             Theme (navy/teal)
requirements.txt        Pinned dependencies
.env.example            Template for secrets (copy to .env; .env is git-ignored)
```

## Security notes

* Secrets and DB credentials live only in `.env` (git-ignored). Never commit it.
* CSRF protection on every form; logout requires POST.
* Profile photo uploads must be real images up to 2 MB.
* With `DJANGO_DEBUG=False`, session and CSRF cookies are marked Secure.
