# CatchLedger

**A Catch Recording and Sales Management System for a Fishermen's Cooperative**

Full-stack Django (templates + Bootstrap 5) with PostgreSQL / Supabase.
This repository contains **Phase 1: the Account feature** and **Phase 2: Catch Delivery Recording**, the system's core feature.

## Phase 2 - Core Feature: Catch Delivery Recording

Every landing is logged once, as a **Delivery** (fisher, boat, date/time) with one or more **DeliveryItem** lines
(species, grade, weight). The price per kilogram is looked up automatically from the price rate in effect on the
landing date and copied onto the item, so later price changes never alter past records (SDD BR-15, BR-16).

| Requirement | Where |
|---|---|
| Models with real relationships (Fisher, Boat, Species, PriceRate, Delivery, DeliveryItem, AuditLog) | `deliveries/models.py` |
| Create a delivery with one or more items, through the UI | `/deliveries/new/` - Recorder or Manager only (BR-06) |
| Read / search deliveries | `/deliveries/` - all three roles can view (filter by fisher name and date range) |
| Update a delivery | `/deliveries/<id>/edit/` - Recorder same calendar day only, Manager any time (BR-07) |
| Delete (as Void, never hard-deleted) | `/deliveries/<id>/void/` - Manager only, reason required, kept for audit (BR-25) |
| Validation | No future landing date (BR-18); weight 0-5,000 kg (BR-19); no duplicate species+grade in one delivery (BR-20); a price rate must exist for the species/grade/date or the item is rejected (BR-15) |
| Tied to Account feature | Every delivery stores `recorded_by` (FK to User); only logged-in Recorders/Managers can create one |
| Role-based access | Enforced with the same `@role_required` decorator from Phase 1; Cashiers can view but not create/edit |
| Auto-generated delivery number | `DLV-YYYYMMDD-NNN`, unique, never reused (BR-21) |
| Audit trail | Create/Update/Void actions on a delivery are written to `AuditLog` (BR-50) |

Master data (Fisher, Boat, Species, PriceRate) can be entered and maintained at `/admin/` for now; a dedicated
Manager-facing UI for these is planned for the next increment (see completion report, Remaining Tasks).

To try it with sample data:

```bash
python manage.py seed_demo_users    # demo_manager / demo_cashier / demo_recorder
python manage.py seed_catch_data    # sample fishers, boats, species and price rates
```

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
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
DATABASE_SSLMODE=require
```

The project **refuses to start without `DATABASE_URL`** and rejects non-PostgreSQL URLs: there is no SQLite fallback.

## Tests

```bash
python manage.py test accounts deliveries
```

42 `accounts` tests cover registration validation, password hashing, login/logout, protected pages, role isolation,
user management and the profile (including photo upload). 9 `deliveries` tests cover role-gated create/edit/void,
future-date rejection, over-weight rejection, missing price rate rejection, and same-day edit restriction. They run
against PostgreSQL; the database user needs the `CREATEDB` privilege so Django can create `test_<name>`.

## Project structure

```
config/                 Django settings (env-driven), root URLs
accounts/               Account feature: User model, forms, views, tests
  management/commands/  seed_demo_users
deliveries/              Core feature: Fisher, Boat, Species, PriceRate, Delivery, DeliveryItem, AuditLog
  management/commands/  seed_catch_data
templates/              base layout, partials, account pages, delivery pages, 403 page
static/css/             Theme (navy/teal)
requirements.txt        Pinned dependencies
.env.example            Template for secrets (copy to .env; .env is git-ignored)
```

## Security notes

* Secrets and DB credentials live only in `.env` (git-ignored). Never commit it.
* CSRF protection on every form; logout requires POST.
* Profile photo uploads must be real images up to 2 MB.
* With `DJANGO_DEBUG=False`, session and CSRF cookies are marked Secure.
