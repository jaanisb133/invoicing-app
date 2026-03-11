# V-Rekini (V-Rekini.lv) — Full Project Context

> **Purpose:** This document captures everything built across the development chat so the next session can pick up with full context.

---

## 1. Project Overview

**Name:** V-Rekini (Pavadzimju Parvaldnieks)
**Domain:** v-rekini.lv
**Server IP:** 204.168.150.114
**What it is:** A Latvian-language invoicing and document management SaaS platform.
**History:** Started as a v1 desktop Tkinter app, then fully rewritten as a v2 web application using FastAPI.
**Target users:** Latvian businesses and freelancers who need to create, manage, and send invoices (rekins) and waybills (pavadzimes).

---

## 2. Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | **FastAPI 0.115.0** (Python, async) |
| Server | **Uvicorn** (1 worker, port 8000) |
| Database | **SQLite 3** — single file at `/opt/vrekini/data/veggie_invoices.db` |
| Templating | **Jinja2** — full server-side rendering |
| Frontend | Vanilla HTML/CSS/JS — no framework, custom monochrome design system |
| Fonts | **DM Sans** (Regular + Bold TTF, supports Latvian characters) |
| PDF Generation | **ReportLab 4.2.2** — 3 invoice templates |
| Auth | **bcrypt** password hashing, **itsdangerous** session cookies |
| Email | **SMTP** (server50.areait.lv:465 SSL) + **Brevo API** fallback |
| Payments | **Stripe** subscriptions with webhook handling |
| Reverse Proxy | **Nginx** with HTTPS (Let's Encrypt) |
| Process Manager | **Systemd** service unit |
| Repository | `https://github.com/jaanisb133/invoicing-app.git` |

---

## 3. Directory Structure

```
/home/user/invoicing-app/          (development)
/opt/vrekini/                      (production deployment)
├── .env                           # SMTP, Stripe, Brevo secrets
├── .gitignore
├── README.md
├── requirements.txt
├── run.py                         # Entry point (uvicorn runner)
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app — 60+ routes
│   ├── database.py                # SQLite layer (1156 lines)
│   ├── pdf_generator.py           # PDF generation (788 lines, 3 templates)
│   ├── fonts/
│   │   ├── DMSans-Bold.ttf
│   │   └── DMSans-Regular.ttf
│   ├── static/
│   │   ├── css/style.css          # Monochrome design system, dark mode
│   │   └── js/
│   └── templates/
│       ├── base.html              # Master layout with sidebar nav
│       ├── dashboard.html         # Stats & recent docs
│       ├── documents.html         # Document listing with filters
│       ├── document_form.html     # Create/edit invoices (36KB)
│       ├── document_view.html     # View, preview, email (26KB)
│       ├── clients.html           # Client CRUD
│       ├── products.html          # Product/service CRUD
│       ├── stock.html             # Inventory dashboard
│       ├── recurring.html         # Recurring invoice management
│       ├── export.html            # Bulk PDF/ZIP export
│       ├── settings.html          # Company & document config (20KB)
│       ├── account.html           # User profile & password
│       ├── pricing.html           # Public pricing page
│       ├── pricing_auth.html      # Authenticated pricing/upgrade
│       ├── login.html
│       ├── register.html
│       ├── set_password.html      # Admin-forced password change
│       ├── billing_success.html
│       ├── users.html             # Admin user management
│       ├── _public_navbar.html
│       └── _pricing_content.html  # Reusable pricing tier cards (11KB)
├── deploy/
│   ├── setup-server.sh            # Full production setup script
│   ├── vrekini.nginx.conf         # Nginx config (HTTPS, security headers)
│   └── vrekini.service            # Systemd unit file
└── data/                          # Runtime data (gitignored)
    ├── veggie_invoices.db         # SQLite database
    ├── dokumenti/                 # Generated PDFs
    └── logos/                     # Uploaded company logos
```

---

## 4. Database Schema

**Location:** Configured via `VREKINI_DB_PATH` env var, defaults to `/data/veggie_invoices.db`
**Engine:** SQLite with `PRAGMA foreign_keys = ON`

### Tables

1. **users** — User accounts & subscription info
   - `id, username, email, password_hash, display_name`
   - `must_change_password, is_admin, tier` (free/starter/business/admin)
   - `subscription_status, subscription_start, subscription_end, billing_cycle`
   - `stripe_customer_id, stripe_subscription_id`
   - `max_documents, max_clients, max_products` (tier-enforced limits)
   - `created_at`

2. **user_settings** — Per-user key/value configuration
   - `id, user_id, key, value` — UNIQUE(user_id, key)

3. **products** — Products/services per user
   - `id, user_id, name, unit, active, created_at`

4. **clients** — Client details per user
   - `id, user_id, name, reg_number, vat_number, legal_address`
   - `bank_name, bank_account, contact_person, phone, email`
   - `active, created_at`

5. **documents** — Invoices and purchase orders
   - `id, user_id, doc_type` (buy/sell), `doc_number, seq_num`
   - `client_id, doc_date, vat_rate, notes`
   - `status, created_at`

6. **document_items** — Line items within documents
   - `id, document_id, product_id, quantity, unit, price_per_unit, total`

7. **doc_sequences** — Document numbering sequences
   - `id, user_id, prefix, last_number, year` — UNIQUE(user_id, prefix, year)

8. **recycled_numbers** — Tracks deleted doc numbers for reuse
   - `id, user_id, doc_type, year, number, recycled_at`

9. **recurring_invoices** — Scheduled auto-generation
   - `id, user_id, doc_type, client_id, vat_rate, notes, template`
   - `frequency, next_run, send_email, active`
   - `items_json` (serialized line items), `created_at`

10. **settings** — Global system settings
    - `key, value`

---

## 5. Features Built (in order of development)

### Phase 1: Foundation
- FastAPI web app with Latvian UI
- 3 PDF invoice templates (Classic, Modern, Minimal) using ReportLab
- SQLite database layer with full CRUD

### Phase 2: Authentication & Multi-Tenancy
- User registration & login (bcrypt + session cookies)
- Multi-tenant data isolation (all queries scoped by user_id)
- Admin user management panel
- Password change page in sidebar
- Stock management toggle in settings

### Phase 3: SaaS Platform
- Transformed into multi-tenant SaaS
- Onboarding gate, invoice preview, logo upload
- Dark/light theme toggle (localStorage)
- Email sending with PDF attachments
- Recurring invoices (monthly auto-generation + email delivery)
- Centralized email service (replaced per-user SMTP config)

### Phase 4: UI/UX Polish
- Minimalistic gray/white/silver color scheme
- Useful dashboard stats (revenue, top clients, top products)
- Document editing with 2-column form + live template preview
- Inline template-styled preview on document view
- Mobile responsiveness (hamburger menu, responsive cards)

### Phase 5: PDF & Document Improvements
- Electronic document declaration (replaces signatures with disclaimer)
- DM Sans font for PDFs (Latvian character support)
- Logo placement with inversion option + width slider
- Document numbering: 3 schemes (year+seq, daily reset, simple sequential)
- Configurable prefixes, separators, digit counts
- Number recycling when documents deleted
- Fix ZIP export, date ranges, formatting bugs

### Phase 6: Business Features
- Export page with bulk PDF/ZIP download
- Stock validation (prevent overselling on document creation)
- Payment status tracking on documents
- Status badge colors, inline status toggle
- Date shortcuts on document list filters

### Phase 7: Production Deployment
- Nginx config with HTTPS, security headers, static file caching
- Systemd service unit with auto-restart
- Let's Encrypt SSL via Certbot
- `setup-server.sh` for one-command server provisioning
- SMTP configured for v-rekini.lv email with SSL
- `.env` loading with explicit path relative to app directory

### Phase 8: Monetization
- Brevo API email integration (with SMTP fallback)
- Stripe subscription billing with 3 tiers:
  - **Free:** 50 docs, 20 clients, 50 products, 5 emails/month
  - **Starter (€9.99/mo):** 500 docs, 100 clients, 200 products, 50 emails/month, recurring
  - **Business (€19.99/mo):** 5000 docs, 500 clients, 1000 products, unlimited emails, all templates
- Stripe webhooks (customer.created, subscription.updated, subscription.deleted)
- Customer portal access for subscription management
- Pricing page (public + authenticated versions)

### Phase 9: Stability Fixes
- Database stability: env var for DB path, single Uvicorn worker (SQLite safety)
- Fixed pricing page crash for logged-in users
- Removed old desktop/ directory artifacts

---

## 6. Key Routes

### Authentication
- `GET/POST /login`, `/register`, `/set-password`, `/logout`

### Dashboard & Account
- `GET /` — Dashboard
- `GET /account`, `POST /account/profile`, `POST /account/password`

### Documents
- `GET /documents` — List (with type/client/date/status filters)
- `GET /documents/new`, `POST /documents/create`
- `GET /documents/{id}`, `GET /documents/{id}/edit`, `POST /documents/{id}/update`
- `GET /documents/{id}/pdf` — Generate/download PDF
- `POST /documents/{id}/send` — Email with PDF attachment
- `POST /documents/{id}/delete`, `POST /documents/{id}/status`

### Products & Clients
- `GET /products`, `POST /products/add`, `POST /products/{id}/edit`, `POST /products/{id}/delete`
- `GET /clients`, `POST /clients/add`, `POST /clients/{id}/edit`, `POST /clients/{id}/delete`
- `POST /api/products/add`, `POST /api/clients/add` — Quick-add API endpoints

### Settings & Admin
- `GET/POST /settings`, `POST /settings/logo`, `POST /settings/logo/delete`
- `GET /api/logo` — Retrieve logo image
- `GET /users`, `POST /users/add`, `POST /users/{id}/delete`

### Stock, Recurring, Export
- `GET /stock`, `GET /api/stock/{product_id}`
- `GET /recurring`, `POST /recurring/create`, `POST /recurring/from-document/{id}`, `POST /recurring/{id}/toggle`, `POST /recurring/{id}/delete`
- `GET /export`, `POST /export/pdf`

### Billing
- `GET /pricing`
- `POST /billing/checkout`, `GET /billing/success`, `POST /billing/portal`
- `POST /stripe/webhook`

### Preview
- `GET /api/invoice-preview` — Real-time invoice preview

---

## 7. Design System

- **Color palette:** Monochrome — dark gray `#111827`, light `#f9fafb`
- **Typography:** DM Sans (Regular + Bold)
- **Border radius:** 8px consistently
- **Dark mode:** Toggle in sidebar, persisted via localStorage
- **Layout:** CSS Grid/Flexbox, responsive with mobile hamburger menu
- **No CSS framework** — all custom CSS in `static/css/style.css`

---

## 8. Deployment & Operations

### Production Server
- **OS:** Linux on 204.168.150.114
- **Domain:** v-rekini.lv (HTTPS via Let's Encrypt)
- **App path:** `/opt/vrekini/`
- **Database:** `/opt/vrekini/data/veggie_invoices.db`
- **PDFs stored:** `/opt/vrekini/data/dokumenti/`
- **Logos stored:** `/opt/vrekini/data/logos/`

### Deploy Process
```bash
ssh root@204.168.150.114
cd /opt/vrekini
git pull origin main
systemctl restart vrekini
```

### Service Management
```bash
systemctl status vrekini
systemctl restart vrekini
journalctl -u vrekini -f    # View logs
```

### Key Config Notes
- **Single Uvicorn worker** — required for SQLite (no concurrent write issues)
- **Database path** via `VREKINI_DB_PATH` env var
- **Secrets** in `.env` file (SMTP, Stripe, Brevo credentials)
- **Nginx** handles SSL termination, static files (7-day cache), 10MB upload limit

---

## 9. Database Safety

The SQLite database (`veggie_invoices.db`) persists independently of code changes. Application upgrades (code deploys) do **not** touch the database file. Data is safe across upgrades as long as:
1. You don't delete the `.db` file
2. You don't run migrations that drop tables
3. You back up the file before major schema changes

**Backup command:**
```bash
cp /opt/vrekini/data/veggie_invoices.db /opt/vrekini/data/veggie_invoices.db.backup-$(date +%Y%m%d)
```

---

## 10. Known Admin Credentials

- **Username:** `admin`
- **Password:** Set via bcrypt hash update (use `set_password` page or manual DB update)
- **Admin flag:** `is_admin = 1` in users table
- Email login is the default (username field exists but email is primary)

---

## 11. Environment Variables (.env)

```
VREKINI_DB_PATH=/opt/vrekini/data/veggie_invoices.db

# Email (SMTP)
SMTP_HOST=server50.areait.lv
SMTP_PORT=465
SMTP_SSL=true
SMTP_USER=rekini@v-rekini.lv
SMTP_PASS=<password>
SMTP_FROM=V-Rekini <rekini@v-rekini.lv>

# Email (Brevo API fallback)
BREVO_API_KEY=<key>
BREVO_SENDER_EMAIL=rekini@v-rekini.lv
BREVO_SENDER_NAME=V-Rekini

# Stripe
STRIPE_SECRET_KEY=<key>
STRIPE_PUBLISHABLE_KEY=<key>
STRIPE_WEBHOOK_SECRET=<secret>
STRIPE_PRICE_STARTER_MONTHLY=<price_id>
STRIPE_PRICE_STARTER_YEARLY=<price_id>
STRIPE_PRICE_BUSINESS_MONTHLY=<price_id>
STRIPE_PRICE_BUSINESS_YEARLY=<price_id>
```

---

## 12. Git History Summary

The project has ~50 commits on the main branch, progressing from:
1. v1 desktop prototype
2. FastAPI web app with 3 PDF templates
3. Auth system + multi-tenant SaaS
4. UI polish (dark theme, mobile, monochrome design)
5. PDF improvements (fonts, logos, numbering)
6. Business features (stock, recurring, export, status tracking)
7. Production deployment (nginx, systemd, SSL)
8. Stripe billing + Brevo email integration
9. Stability fixes

---

## 13. What to Work On Next (Potential)

These are areas that may need attention in future sessions:
- Stripe price IDs need to be configured in `.env` for billing to work
- Brevo API key needs to be set if using Brevo for email
- Database migrations strategy for schema changes
- Automated backups for the SQLite database
- Rate limiting / abuse prevention
- Password reset via email flow
- Multi-language support (currently Latvian-only)
- Dashboard chart visualizations
- Client-side form validation improvements
- Automated testing (no tests exist currently)
