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
| Payments | **EveryPay / SEB E-commerce** API v4 (card tokenization + MIT recurring) |
| Reverse Proxy | **Nginx** with HTTPS (Let's Encrypt) |
| Process Manager | **Systemd** service unit |
| Repository | `https://github.com/jaanisb133/invoicing-app.git` |

---

## 3. Directory Structure

```
/home/user/invoicing-app/          (development)
/opt/vrekini/                      (production deployment)
├── .env                           # SMTP, EveryPay, Brevo secrets
├── .gitignore
├── README.md
├── requirements.txt
├── run.py                         # Entry point (uvicorn runner)
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app — 80+ routes
│   ├── database.py                # SQLite layer (1156 lines)
│   ├── pdf_generator.py           # PDF generation (788 lines, 3 templates)
│   ├── everypay.py                # EveryPay/SEB payment API client (oneoff, MIT, refund)
│   ├── einvoice.py                # E-invoice XML generator (PEPPOL BIS 3.0)
│   ├── registry.py               # Latvian business registry search (UR open data)
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
│       ├── export.html            # Bulk PDF/ZIP + e-invoice XML export
│       ├── settings.html          # Company & document config (20KB)
│       ├── account.html           # User profile & password
│       ├── pricing.html           # Public pricing page
│       ├── pricing_auth.html      # Authenticated pricing/upgrade
│       ├── login.html
│       ├── register.html
│       ├── set_password.html      # Admin-forced password change
│       ├── billing_success.html
│       ├── users.html             # Admin user management
│       ├── setup.html             # First-time onboarding (company info)
│       ├── contacts.html          # SEB compliance: company contact info
│       ├── terms.html             # SEB compliance: payment terms & policies
│       ├── _public_navbar.html
│       ├── _public_footer.html    # Footer with payment/bank logos
│       ├── _pricing_content.html  # Reusable pricing tier cards (11KB)
│       └── _upgrade_gate.html     # Reusable PRO upgrade overlay
├── deploy/
│   ├── setup-server.sh            # Full production setup script
│   ├── vrekini.nginx.conf         # Nginx config (HTTPS, security headers)
│   ├── vrekini.service            # Systemd unit file
│   └── update-registry.sh        # Daily business registry CSV download + import
└── data/                          # Runtime data (gitignored)
    ├── veggie_invoices.db         # SQLite database
    ├── registry.db                # Business registry search DB (separate)
    ├── register.csv               # Downloaded UR open data CSV (~120MB)
    ├── dokumenti/                 # Generated PDFs
    └── logos/                     # Uploaded company logos
```

---

## 4. Database Schema

**Location:** Configured via `VREKINI_DB_PATH` env var, defaults to `/data/veggie_invoices.db`
**Engine:** SQLite with `PRAGMA foreign_keys = ON`

### Tables

1. **users** — User accounts & subscription info
   - `id, username, email, password_hash, display_name, phone`
   - `must_change_password, is_admin, tier` (free/starter/business/admin)
   - `subscription_status, subscription_start, subscription_end, billing_cycle`
   - `everypay_token, everypay_payment_ref`
   - `max_documents, max_clients, max_products` (tier-enforced limits)
   - `created_at`

2. **user_settings** — Per-user key/value configuration
   - `id, user_id, key, value` — UNIQUE(user_id, key)

3. **products** — Products/services per user
   - `id, user_id, name, unit, active, created_at`

4. **clients** — Client details per user
   - `id, user_id, name, reg_number, vat_number, vat_payer` (0/1), `legal_address`
   - `bank_name, bank_account, contact_person, phone, email`
   - `active, created_at`

5. **documents** — Invoices and purchase orders
   - `id, user_id, doc_type` (buy/sell), `doc_number, seq_num`
   - `client_id, doc_date, vat_rate, notes, payment_due_date`
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

10. **email_log** — Tracks emails sent per user (for monthly limit enforcement)
    - `id, user_id, document_id, recipient, sent_at`

11. **settings** — Global system settings
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
  - **Free:** 5 docs, 3 clients, 3 products, 0 emails, no recurring, classic template only
  - **Starter (€9.99/mo):** 500 docs, 100 clients, 200 products, 50 emails/month, recurring, all templates, e-invoice, export
  - **Business (€19.99/mo):** 5000 docs, 500 clients, 1000 products, unlimited emails, all features
- Stripe webhooks (customer.created, subscription.updated, subscription.deleted)
- Customer portal access for subscription management
- Pricing page (public + authenticated versions)

### Phase 9: Stability Fixes
- Database stability: env var for DB path, single Uvicorn worker (SQLite safety)
- Fixed pricing page crash for logged-in users
- Removed old desktop/ directory artifacts

### Phase 9b: SEB E-Commerce Compliance & Subscription Revamp
- **SEB compliance pages** (required for payment processing):
  - `/contacts` — company info (SIA "VN Media", reg number 40203543358, address, email, phone)
  - `/terms` — payment methods, 3D Secure info, refund/return policy, support hours
  - Both pages accessible without authentication
  - Public footer (`_public_footer.html`) with payment logos (Visa, Mastercard, Google Pay, Apple Pay) and partner logos (EveryPay, SEB, Citadele, LHV)
  - Footer rendered on all public pages (login, register, pricing, contacts, terms)
- **Pricing & subscription revamp:**
  - Full-width subscription management page ("Mans abonements") at `/pricing` (authenticated)
  - Current plan highlighted with border/background
  - Usage bars showing docs/clients/products consumed vs. limit
  - Plan/billing cycle passed through registration → auto-checkout after signup
  - Admin can change any user's tier via dropdown in `/users` panel (`POST /users/{id}/tier`)
- **Entity type switcher:**
  - Individual ("Fiziska persona") vs. business ("Juridiska persona") toggle
  - Available in `/setup` onboarding and `/settings`
  - Changes registration label: "Reģ.Nr." for business, "Personas kods" for individual
  - Affects invoice PDF party labels
- **Simplified onboarding:**
  - New `/setup` page shown on first login (replaces old onboarding gate)
  - Collects: entity type, company name, reg number, legal address, bank details
  - Mobile zoom prevention (viewport meta, 16px minimum font on inputs)
- **VAT payer toggle:**
  - User-level setting "Ir PVN maksātājs?" in setup and settings
  - Non-VAT payers: PVN fields hidden throughout the app, 0% VAT on documents
  - VAT payers: full PVN number field and VAT rate selection visible
- **Phone field** added to users table, registration form, and account page
  - Included in e-invoice XML contact details (PEPPOL BIS 3.0)

### Phase 9c: Tier-Based Feature Gating
- **PRO badges** in sidebar navigation for restricted features
- **Blurred overlay** (`_upgrade_gate.html`) with lock icon and upgrade CTA on:
  - Recurring invoices page (free plan)
  - Export page (free plan)
  - Stock management page (free plan)
- **Template restrictions:**
  - Free plan: classic template only
  - All templates visible/previewable on document view, but download gated
  - PRO templates show "Uzlabot plānu" (upgrade) button instead of download
  - E-invoice XML button shows PRO badge for free users
- **Backend enforcement** on all gated API routes (returns 403 for unauthorized tiers)
- **Clickable document rows** — clicking a row navigates to document view (ignores clicks on menus/badges/buttons)

### Phase 10: Accounting Export & Document Enhancements
- **Accounting export** (`POST /export/accounting`) — generates Excel (.xlsx) via openpyxl with 2 sheets:
  - Sheet 1 "Dokumenti": one row per document with configurable columns
  - Sheet 2 "Pozīcijas": one row per line item with configurable columns
- **Built-in presets** for Latvian accounting software: Horizon, Jumis, Zalktis
- **Custom preset builder** — users can create/save/edit/delete custom column configurations via modal UI
  - Drag-to-reorder columns, field source selection, constant values, date formatting
  - Saved as JSON in `user_settings` table with key `accounting_preset_<name>`
- **Preset API routes:** `POST /api/accounting-presets/save`, `GET /api/accounting-presets`
- **Payment due date system:**
  - Default setting `payment_due_days` in settings (auto-calculates from doc_date)
  - Per-document datepicker override on document form
  - `payment_due_date` column in documents table
- **VAT payer status on clients:**
  - `vat_payer` field (0/1) on clients table
  - Checkbox "Ir PVN maksātājs?" in add/edit client modals
  - Auto-checks when PVN number is entered
  - Exports as "M" (vat payer) or "X" (non-payer) in `vat_category` column
- **Document type codes:** Export uses "Pirk." (buy) / "Pārd." (sell) instead of raw type values
- **30+ export field types** available for column configuration (doc info, client data, company data, line items, calculated totals)
- **Documents list:** Replaced PVN % column with total invoice sum (with VAT)
- **Custom email text:** Editable default email template in settings with `{doc_type}`, `{doc_number}`, `{date}`, `{company}` placeholders
- **Send popup:** "Pielāgot e-pasta ziņojumu" checkbox reveals editable textarea with pre-filled default text
- **Email date format:** Changed from yyyy-mm-dd to dd.mm.yyyy

### Phase 11: E-invoice Export (PEPPOL BIS Billing 3.0)
- **E-invoice XML generator** (`app/einvoice.py`) — generates structured e-invoices in UBL 2.1 XML format
- **Standard compliance:** PEPPOL BIS Billing 3.0, LVS EN 16931-1:2017 (mandatory in Latvia from 2028)
- **Single document download:** `GET /documents/{id}/einvoice` — downloads one XML file
- **Bulk export:** `POST /export/einvoice` — ZIP archive of multiple e-invoice XML files with date/type filters
- **UI integration:**
  - "E-rēķins XML" button on document view page (next to PDF download)
  - Dedicated e-invoice export card on /export page with date range, type filter, preview
- **Unit code mapping:** Latvian unit names (kg, gab, kaste, etc.) mapped to UN/ECE Recommendation 20 codes (KGM, C62, CT, etc.)
- **Tax categories:** Automatic S (standard) / Z (zero-rate) determination based on VAT rate
- **Payment means:** Includes bank account (IBAN) and credit transfer info from seller settings
- **XML structure:** CustomizationID, ProfileID, InvoiceTypeCode (380), parties with EndpointID, TaxTotal, LegalMonetaryTotal, InvoiceLines
- **VID reference:** https://www.vid.gov.lv/lv/e-rekini

### Phase 12: UI Action Menus & Tier Gating
- **Document view page** — consolidated 6+ action buttons into cleaner layout:
  - **Split download button** with dropdown: PDF download (main button) + chevron opens dropdown with PDF and E-rēķins XML options
  - **3-dot menu** for remaining actions: Nosūtīt klientam, Rediģēt, Periodiskais rēķins, Atzīmēt kā apmaksātu/izrakstītu
  - Both menus use `position: fixed` dropdowns with viewport clamping (same pattern as document list)
- **Document list 3-dot menu** — added two new actions:
  - "Nosūtīt klientam" — opens send-email modal with client email pre-filled from JS lookup map
  - "Periodiskais rēķins" — opens recurring invoice modal
  - Both use shared modals at page level, populated dynamically via `data-action` / `data-doc-id` / `data-client-id` attributes
  - Fixed click handler bug: switched from inline `onclick` on `<a>` tags (swallowed by centralized handler) to `data-action` buttons handled explicitly
- **Dashboard 3-dot menu** — replaced simple "Skatīt" button with full menu matching documents list:
  - Skatīt, Rediģēt, Lejupielādēt PDF, E-rēķins XML, Nosūtīt klientam, Periodiskais rēķins, status toggle, Dzēst
  - Added status column to dashboard table (when status tracking enabled)
  - Reduced recent docs from 10 to 5
  - Added send-email and recurring-invoice modals
- **Free plan gating** on all 3 pages (document view, document list, dashboard):
  - "Nosūtīt klientam" disabled with PRO badge for free users → links to /pricing
  - "Periodiskais rēķins" disabled with PRO badge for free users → links to /pricing
  - Template flags: `email_enabled` and `recurring_enabled` passed from all 3 route handlers
- **Email usage tracking:**
  - New `email_log` table records every sent email (user, document, recipient, timestamp)
  - `get_emails_sent_this_month()` counts emails in current calendar month
  - `log_email_sent()` records successful sends
  - Send endpoint enforces limits: free plan blocked entirely, starter capped at 50/month, business/admin unlimited
  - Error message shown when monthly limit exceeded

### Phase 13: Business Registry Search & VAT Validation
- **Latvian Business Registry integration** (`app/registry.py`):
  - Downloads official open data CSV from `dati.ur.gov.lv/register/register.csv` (~120MB, updated daily)
  - Imports into separate SQLite database (`data/registry.db`) for fast lookups
  - Columns: `regcode` (reg number), `name`, `type_text` (entity type), `address`, `registered`, `terminated`
  - Search endpoint: `GET /api/registry/search?q=...` — searches by name (LIKE) or regcode (prefix match)
  - Prioritizes starts-with matches over contains; filters out terminated businesses
  - Status endpoint: `GET /api/registry/status` (admin only) — shows record count
- **Autocomplete UI** on all client forms:
  - Add client modal (`clients.html`) — name field has registry autocomplete dropdown
  - Quick-add client modal (`document_form.html`) — same autocomplete
  - Type 2+ characters → debounced search (250ms) → dropdown with company name, regcode, type, address
  - Keyboard navigation (↑↓ to browse, Enter to select, Esc to close)
  - Selecting a result auto-fills: name, registration number, legal address
  - Hint text "Meklē Uzņēmumu reģistrā" below the name field
- **VIES VAT validation** (`GET /api/vat/validate?vat_number=...`):
  - Validates EU VAT numbers via the EC VIES SOAP service
  - Returns valid/invalid status, registered name, and address
  - Auto-detects country code (defaults to LV if omitted)
  - "Pārbaudīt VIES" button on all VAT number fields (add, edit, quick-add modals)
  - Shows green checkmark (valid) or red X (invalid) with company name
- **Daily auto-refresh** via cron (`deploy/update-registry.sh`):
  - Downloads CSV, validates line count, imports into registry.db
  - Cron: `0 4 * * *` (daily at 4 AM)
  - Logs to `/var/log/vrekini-registry.log`
  - Setup script adds cron job and runs initial import

---

## 6. Key Routes

### Authentication
- `GET/POST /login`, `/register`, `/set-password`, `/logout`

### Onboarding & Account
- `GET /setup`, `POST /setup` — First-time onboarding
- `GET /` — Dashboard
- `GET /account`, `POST /account/profile`, `POST /account/password`

### Documents
- `GET /documents` — List (with type/client/date/status filters)
- `GET /documents/new`, `POST /documents/create`
- `GET /documents/{id}`, `GET /documents/{id}/edit`, `POST /documents/{id}/update`
- `GET /documents/{id}/pdf` — Generate/download PDF
- `GET /documents/{id}/einvoice` — Download e-invoice XML (PEPPOL BIS 3.0)
- `POST /documents/{id}/send` — Email with PDF attachment
- `POST /documents/{id}/delete`, `POST /documents/{id}/status`

### Products & Clients
- `GET /products`, `POST /products/add`, `POST /products/{id}/edit`, `POST /products/{id}/delete`
- `GET /clients`, `POST /clients/add`, `POST /clients/{id}/edit`, `POST /clients/{id}/delete`
- `POST /api/products/add`, `POST /api/clients/add` — Quick-add API endpoints

### Public Pages (SEB Compliance)
- `GET /contacts` — Company contact information
- `GET /terms` — Payment terms, refund policy, security info

### Settings & Admin
- `GET/POST /settings`, `POST /settings/logo`, `POST /settings/logo/delete`
- `GET /api/logo` — Retrieve logo image
- `GET /users`, `POST /users/add`, `POST /users/{id}/delete`, `POST /users/{id}/tier`

### Stock, Recurring, Export
- `GET /stock`, `GET /api/stock/{product_id}`
- `GET /recurring`, `POST /recurring/create`, `POST /recurring/from-document/{id}`, `POST /recurring/{id}/toggle`, `POST /recurring/{id}/delete`
- `GET /export`, `POST /export/pdf`, `POST /export/einvoice`, `POST /export/accounting`
- `POST /api/accounting-presets/save`, `GET /api/accounting-presets`

### Billing
- `GET /pricing`
- `POST /billing/checkout`, `GET /billing/return`, `POST /billing/cancel`
- `GET /everypay/callback`

### Business Registry & VAT
- `GET /api/registry/search?q=...` — Search Latvian business registry by name or regcode
- `GET /api/registry/status` — Registry DB record count (admin only)
- `GET /api/vat/validate?vat_number=...` — Validate EU VAT number via VIES

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
# IMPORTANT: always update the systemd service after pull (in case it changed)
sudo cp deploy/vrekini.service /etc/systemd/system/vrekini.service
sudo systemctl daemon-reload
sudo systemctl restart vrekini
# Verify it started cleanly (no port conflict errors)
sudo journalctl -u vrekini --no-pager -n 10
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
- **Secrets** in `.env` file (SMTP, EveryPay, Brevo credentials)
- **Nginx** handles SSL termination, static files (7-day cache), 10MB upload limit

### IMPORTANT: Only One App Instance (Resolved 2026-03-12)
There must be exactly **one** systemd service and **one** app directory on the server:
- **Service:** `vrekini.service` only — no other service should run uvicorn on port 8000
- **App path:** `/opt/vrekini/` only — no other copies should exist

**Root cause of the "ghost app" problem:** An old `invoicing.service` running from `/opt/invoicing/` was competing with `vrekini.service` for port 8000. The old service always won (started first), so the site served stale code and a different database. Fixed by disabling/removing `invoicing.service` and deleting `/opt/invoicing/` and `/tmp/invoicing-new/`.

**If the site ever shows old/wrong content again**, check:
```bash
# Only vrekini.service should appear — nothing else with "invoic" in the name
sudo systemctl list-units --type=service --all | grep -i invoic
# Only ONE uvicorn from /opt/vrekini should appear
ps aux | grep uvicorn
# Only ONE database should exist
sudo find / -name "veggie_invoices.db" 2>/dev/null
```

### Zombie Process Prevention
The systemd service includes safeguards against orphan uvicorn processes:
- **`KillMode=control-group`** — kills ALL processes in the service group, not just the main PID
- **`ExecStartPre=fuser -k 8000/tcp`** — kills any stale process on port 8000 before starting
- **`StartLimitBurst=5` / `StartLimitIntervalSec=60`** — stops infinite restart loops (in `[Unit]` section)

**If it ever happens again:** `sudo fuser -k 8000/tcp && sleep 2 && sudo systemctl restart vrekini`

**Never run `run.py` on the production server** — it's for local development only.

---

## 9. Database — Safety, Backups & Recovery

### CRITICAL: Do Not Lose Data
The SQLite database (`veggie_invoices.db`) contains ALL user data — clients, products, invoices, settings, everything. There is no cloud sync or automatic backup. **If this file is lost or corrupted, the data is gone.** Always back up before major changes.

### Where the Data Lives
- **Production database:** `/opt/vrekini/data/veggie_invoices.db`
- **Generated PDFs:** `/opt/vrekini/data/dokumenti/`
- **Uploaded logos:** `/opt/vrekini/data/logos/`
- **Backups:** `/opt/vrekini/data/` (same folder, with `.backup-` suffix)

### Data Persistence
The database persists independently of code changes. Application upgrades (code deploys via `git pull`) do **not** touch the database file. Data is safe across upgrades as long as:
1. You don't delete the `.db` file
2. You don't run migrations that drop tables
3. You back up the file before major schema changes

### Backup Commands (run on the server)

**Create a backup (one per day — overwrites if run multiple times same day):**
```bash
cp /opt/vrekini/data/veggie_invoices.db /opt/vrekini/data/veggie_invoices.db.backup-$(date +%Y%m%d)
```

**Create a backup with timestamp (safe for multiple backups per day):**
```bash
cp /opt/vrekini/data/veggie_invoices.db /opt/vrekini/data/veggie_invoices.db.backup-$(date +%Y%m%d-%H%M%S)
```
This creates filenames like: `veggie_invoices.db.backup-20260312-143025`

**View all backups:**
```bash
ls -la /opt/vrekini/data/*.backup-*
```

### Download Database to Local Machine (run from YOUR computer, not the server)

**Download the live database:**
```bash
scp root@204.168.150.114:/opt/vrekini/data/veggie_invoices.db ~/Downloads/veggie_invoices.db
```

**Download a specific backup (use its full filename):**
```bash
scp root@204.168.150.114:/opt/vrekini/data/veggie_invoices.db.backup-20260312-143025 ~/Downloads/veggie_invoices.db.backup-20260312-143025
```

**List available backups before downloading (run from your computer):**
```bash
ssh root@204.168.150.114 "ls -la /opt/vrekini/data/*.backup-*"
```

### Restore from a Backup (run on the server)
```bash
# Replace the date with the backup you want to restore
cp /opt/vrekini/data/veggie_invoices.db.backup-20260312 /opt/vrekini/data/veggie_invoices.db

# IMPORTANT: restart the app after restoring
systemctl restart vrekini
```

### Quick Reference — Full Workflow
```bash
# 1. Create a backup
cp /opt/vrekini/data/veggie_invoices.db /opt/vrekini/data/veggie_invoices.db.backup-$(date +%Y%m%d-%H%M%S)

# 2. View all backups
ls -la /opt/vrekini/data/*.backup-*

# 3. Download to your computer (run FROM YOUR LOCAL MACHINE)
scp root@204.168.150.114:/opt/vrekini/data/veggie_invoices.db ~/Downloads/

# 4. Restore from a specific backup (replace filename with the one you want)
cp /opt/vrekini/data/veggie_invoices.db.backup-20260312-143025 /opt/vrekini/data/veggie_invoices.db

# 5. Restart app after restore
systemctl restart vrekini

# 6. Navigate back to working directory
cd /opt/vrekini
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

# EveryPay / SEB E-commerce
EVERYPAY_API_USERNAME=<16-char api username>
EVERYPAY_API_SECRET=<api secret>
EVERYPAY_ACCOUNT_NAME=<processing account, e.g. EUR3D1>
EVERYPAY_API_URL=https://igw-seb-demo.every-pay.com/api/v4
```

---

## 12. Git History Summary

The project has ~70 commits on the main branch, progressing from:
1. v1 desktop prototype
2. FastAPI web app with 3 PDF templates
3. Auth system + multi-tenant SaaS
4. UI polish (dark theme, mobile, monochrome design)
5. PDF improvements (fonts, logos, numbering)
6. Business features (stock, recurring, export, status tracking)
7. Production deployment (nginx, systemd, SSL)
8. EveryPay/SEB billing + Brevo email integration
9. Stability fixes
10. SEB e-commerce compliance (contacts, terms, footer, payment logos)
11. Subscription revamp (usage bars, plan highlighting, admin tier control)
12. Entity type switcher, simplified onboarding, VAT payer toggle
13. Tier-based feature gating (PRO badges, blurred overlays, template restrictions)
14. Accounting export with custom preset builder
15. E-invoice export (PEPPOL BIS Billing 3.0 / LVS EN 16931-1:2017)
16. UI action menus (split download button, 3-dot menus on all doc pages) + email tracking
17. Business registry search (UR open data) + VIES VAT validation

---

## 13. EveryPay / SEB E-commerce Payment Integration

### Overview
Payments are handled by **EveryPay** (SEB's payment gateway partner) via the **SEB E-commerce API v4**.
The integration uses card tokenization + MIT (Merchant Initiated Transactions) for recurring billing.

### API Credentials
- **API Username:** `c320faeb8b372194` (16 characters)
- **API Secret:** stored in `.env` as `EVERYPAY_API_SECRET`
- **Processing Account:** `EUR3D1` (determines currency and payment methods)
- **Merchant:** SIA VN MEDIA

### API Endpoints
| Environment | Base URL |
|-------------|----------|
| **Test/Demo** | `https://igw-seb-demo.every-pay.com/api/v4` |
| **Production** | `https://payment.ecommerce.sebgroup.com/api/v4` |

### Merchant Portal
| Environment | Portal URL |
|-------------|-----------|
| **Test** | SEB Testa portāls (where credentials were obtained) |
| **Production** | SEB production merchant portal |

### Payment Flow

**Initial subscription (one-off + tokenization):**
```
1. User clicks upgrade → POST /billing/checkout
2. App calls POST /v4/payments/oneoff (request_token=true, token_agreement=recurring)
3. EveryPay returns payment_link → user redirected to hosted payment page
4. User pays (card/bank/Apple Pay/Google Pay)
5. EveryPay redirects user to GET /billing/return?payment_reference=xxx
6. App calls GET /v4/payments/{ref} to verify status
7. If settled → extract cc_details.token, activate subscription
8. EveryPay also sends callback to GET /everypay/callback (backup confirmation)
```

**Recurring charge (MIT — no user interaction):**
```
1. Cron job finds users due for renewal (subscription_end reached)
2. POST /v4/payments/mit (token_agreement=recurring, amount, stored token)
3. POST /v4/payments/charge (payment_reference + token_details.token)
4. If settled → extend subscription_end by 30/365 days
```

**Cancellation:**
```
1. User clicks cancel → POST /billing/cancel
2. App deactivates card token via POST /v4/tokens/deactivate
3. User downgraded to free tier
```

### Subscription Plans & Prices

| Plan | Monthly | Yearly |
|------|---------|--------|
| Starter (Sākums) | 9.99 EUR | 97.99 EUR |
| Business (Bizness) | 19.99 EUR | 195.99 EUR |

Prices are defined in `app/everypay.py:PLAN_PRICES`.

### Database Fields (users table)
- `everypay_token` — stored card token for recurring MIT charges
- `everypay_payment_ref` — reference of the last payment
- `subscription_status` — active / cancelled / past_due
- `subscription_start` / `subscription_end` — subscription period
- `billing_cycle` — monthly / yearly
- `tier` — free / starter / business

### Callback URL Configuration
The callback URL must be configured in the **SEB Merchant Portal** under **E-shop settings**.
EveryPay sends GET requests to this URL with `payment_reference`, `order_reference`, and `event_name` parameters.

**IMPORTANT — Callback URL is NOT set via API.** It must be configured manually in the merchant portal.
There is no API endpoint or setting in code to configure this — it's a portal-only setting.

| Environment | Callback URL to set |
|-------------|-------------------|
| **Test** | `https://v-rekini.lv/everypay/callback` (or ngrok URL for local testing) |
| **Production** | `https://v-rekini.lv/everypay/callback` |

The callback is a backup mechanism — the primary payment verification happens on user return
(`GET /billing/return`), which checks payment status directly via the API.

### Test Cards
Test cards are available from the SEB merchant test portal under "Testa kartes".
Only test cards must be used in the demo environment. The 3DS simulator password is `secret`.

### Going Live Checklist
When switching from test to production:

1. **Change `EVERYPAY_API_URL`** in `.env`:
   ```
   # FROM (test):
   EVERYPAY_API_URL=https://igw-seb-demo.every-pay.com/api/v4
   # TO (production):
   EVERYPAY_API_URL=https://payment.ecommerce.sebgroup.com/api/v4
   ```

2. **Get production API credentials** from the SEB production merchant portal (new username + secret)

3. **Update callback URL** in the **production** SEB merchant portal:
   → Set to `https://v-rekini.lv/everypay/callback`

4. **Verify processing account** — production may have a different `EVERYPAY_ACCOUNT_NAME`

5. **Set up recurring billing cron** — daily job to call `everypay.charge_mit()` for due subscriptions

### Onboarding Flow (post-registration)
Both signup paths converge through onboarding before payment:

| Step | Path A (plan pre-selected) | Path B (no plan) |
|------|---------------------------|-------------------|
| 1 | Register (plan stored as `_pending_plan`) | Register |
| 2 | Onboarding (/setup — company info, numbering) | Onboarding (/setup) |
| 3 | Auto-checkout via /pricing?upgrade=plan | Show plans page (/pricing) |
| 4 | EveryPay payment → Dashboard | Choose plan or skip → Dashboard |

The `_pending_plan` and `_pending_plan_cycle` user settings bridge registration and post-onboarding checkout.
After onboarding (`/setup` POST), if no pending plan exists, user is shown the plans page.

### API Documentation Reference
Full SEB E-commerce API v4 docs: https://support.ecommerce.sebgroup.com/lv/
(Requires portal access — the API spec covers: payments, shops, processing accounts, mobile payments, agreements, refunds, tokens)

---

## 14. What to Work On Next (Potential)

These are areas that may need attention in future sessions:
- Recurring billing cron job (daily task to auto-charge users via MIT — `db.get_users_due_for_renewal()` + `everypay.charge_mit()` are ready, needs scheduler)
- Recurring invoice auto-emails not yet tested in production
- Database migrations strategy for schema changes
- Automated backups for the SQLite database
- Password reset via email flow
- Multi-language support (currently Latvian-only)
- Dashboard chart visualizations
- Client-side form validation improvements
- Automated testing (no tests exist currently)
