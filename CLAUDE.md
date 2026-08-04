# V-Rēķini — Project Context

Latvian invoicing SaaS built with FastAPI + Jinja2 + SQLite. The user is
building this as a portfolio piece, so it needs to be **impressive both
visually and functionally** — a near-monochrome premium aesthetic with
genuinely modern UX patterns, not generic "AI dashboard" defaults.

## Stack
- **Backend:** FastAPI (`app/main.py`), SQLite (`app/database.py`), ReportLab for PDFs (`app/pdf_generator.py`)
- **Templates:** Jinja2, located in `app/templates/`
- **Frontend:** Vanilla JS, Chart.js 4.4.4, flatpickr for date pickers
- **Styling:** Single `app/static/css/style.css` file (versioned via `?v=N` query string in `base.html`)
- **Fonts:** DM Sans + Inter from Google Fonts (with offline fallback)

## Architecture notes
- Multi-tenant SaaS — all business data isolated per `user_id`
- Tier-gated features (free/mini/starter/business/admin) via `tier_limits` dict
- `_base_context()` provides common template vars: `current_user`, `tier`, `tier_label`, `tier_limits`, `stock_enabled`, `needs_setup`, `offline_mode`
- Dashboard stats API: `/api/dashboard-stats?date_from=&date_to=` returns JSON used for AJAX refresh on date-range changes
- Document table query (`db.get_documents()`) returns `total_with_vat` computed via SQL subquery

## Current design system (post-redesign)

### Color palette — strict near-monochrome
- `--primary: #09090b` (near-black)
- `--bg: #fafaf9` (off-white)
- `--bg-card: #ffffff`
- `--text: #09090b`
- `--text-light: #71717a`
- `--text-lighter: #a1a1aa`
- `--border: #e4e4e7`
- Dark theme inverts to `--bg: #09090b`, `--bg-card: #18181b`
- Accent default for PDFs/invoices: `#09090b` (changeable in settings)
- **No bright accent colors anywhere structural** — colored only used for status (success green, danger red, warning yellow) and they are muted/desaturated

### Typography
- Sidebar/nav: 13px medium weight, no uppercase
- Page H2 headings: 22px, weight 600, letter-spacing -0.5px
- Dashboard greeting H1: 28px (mobile 24px), weight 700, -0.8px
- Table headers: lowercase, weight 500, no uppercase
- Badges: lowercase, 4px radius, border-based not pill

### Layout
- Sidebar: 240px wide, dark `#09090b`, hair border `#18181b`
- Cards: no shadow, hair `--border` only, 10px radius
- Page header: transparent, no border/shadow, 28px top padding
- Stat cards: left-aligned, label above value (label first, then value)
- Buttons: near-black primary, hair-bordered outlines

## What's been built

### Phase 1: Premium minimal redesign (done, approved)
Killed the bright-blue "generic AI dashboard" look. Switched to strict
near-monochrome. User said "looks premium now."

### Phase 2: Dashboard layout + mobile cards (in progress, partial)
- **Dashboard greeting:** "Sveiki, {display_name or company_name}." in 28px bold (mobile 24px) at top of `page-body`
- **Comparison stats:** `get_dashboard_stats_range()` now returns `revenue_change` and `doc_count_change` percentages vs previous period (see "Comparison period logic" below). Displayed as colored badges (`.stat-change.up/.down/.neutral`) under stat values
- **Mobile quick actions:** Two large buttons ("+ Jauns dokuments" / "Visi dokumenti") in 2-column grid, replacing the desktop header buttons on screens ≤768px
- **Mobile table cards:** `.mobile-cards tbody tr` now renders as card with rounded border + padding, flex-wrap layout; `.mobile-card-title` (bold, full-width) + `.mobile-card-meta` (small, muted) replace the verbose LABEL:VALUE rows
- **Dashboard recent docs mobile:** `.dash-recent-mobile` class makes recent docs a tight inline row (number + truncated client name + amount), hiding type badges and dates
- **Client/Product/Document templates** updated with `mobile-card-title` and `mobile-card-meta` classes

### Comparison period logic (`get_dashboard_stats_range` in `app/database.py`)
**Current behavior (fixed):** Calendar shift, not a sliding window.
- `compare_mode='month'` → both endpoints shift back one calendar month
  (May 1-17 → April 1-17). A *full* calendar month snaps to the full prior
  month (April 1-30 → March 1-31).
- `compare_mode='year'` → same, shifted back one calendar year.
- `compare_mode='auto'` (default) → full-year → year; full-month or span
  ≤ 31 days → month; else year.

**In-progress periods are clamped to today.** A range ending in the future
(e.g. "Šomēnes" = Aug 1-31 while today is Aug 4) compares only its *elapsed*
part — Aug 1-4 vs July 1-4, never Aug 1-4 vs all of July. Both sides use the
same elapsed window, so the percentage is like-for-like. The returned dict
carries `cmp_from` / `cmp_to` / `period_in_progress` alongside `prev_from` /
`prev_to` so the window in play is always inspectable.

This fixed a bug where clicking "Šomēnes" reported a ~87% revenue collapse on
flat data, and the figure changed again on refresh (the button set the range
to month-end while the server default used today, and AJAX never synced the
URL). The preset button now uses month-to-date and `loadStats()` writes the
range into the URL via `history.replaceState`.

## What still needs work (user's portfolio vision)

The user shared a mockup of a dark-themed mobile dashboard they like the feel
of: large personalized greeting, prominent stat with "+24%" accent, two
compact secondary stats, full-width CTA button, simple list nav with
chevrons. They said the current dashboard "is still so simple" — they want
the app to feel **"alive" and "cool"**, not just minimal-but-empty.

### Done since that list was written
- ✅ **Comparison period logic** — calendar shift + elapsed-window clamp (see above)
- ✅ **Sparklines on stat cards** — `renderSpark()` in `dashboard.html` draws inline
  SVG (no library) for Apgrozījums / Dokumenti / Vid. rēķins from the
  `spark_revenue` / `spark_docs` / `spark_avg` arrays. Series are gap-free and
  bucketed to ≤ ~60 points for long ranges. Line draws in on first paint.
  "Neapmaksāti" deliberately has none — it's a point-in-time snapshot, not a trend.
- ✅ **Empty states with personality** — `_empty_state.html` macro (mark + title +
  one line + CTA), used on dashboard, documents, clients, products, offers, stock.
  `/documents` distinguishes "no documents yet" from "no match for these filters"
  (the latter offers "Notīrīt filtrus").
- ✅ **Loading states** — shimmer skeletons on the stat values/badges and a dimmed
  chart while the date-range fetch is in flight.
- ✅ **Micro-interactions** — press feedback on controls, stat count-up, sparkline
  draw-in, chart entrance animation, keyboard focus rings. All of it is gated on
  `prefers-reduced-motion`.
- ✅ **Bottom nav on mobile** and **PWA manifest** — already shipped earlier.

### Still open
1. **Hero stat treatment** — make the primary revenue card more visually dominant on mobile (larger type, accent for change %)
2. **List redesign on mobile** — swipe actions for mark-paid/delete; sticky filter bar that collapses on scroll (FAB already exists)
3. **Dashboard "alive" feel** — upcoming due dates highlighted, "X days since last invoice" prompts (recent activity feed exists)
11. **Document view page** — likely needs mobile work; PDF preview probably overflows
12. **Settings page** — large form, mobile UX likely needs grouping/accordion
13. **Invoice templates preview** — the live preview on document_form.html is desktop-only (`@media max-width: 1100px` stacks it)

## Critical files to know
- `app/main.py:1408` — `dashboard()` route, sets up `range_stats` and `range_stats_json`
- `app/main.py:1447` — `/api/dashboard-stats` AJAX endpoint
- `app/main.py:280` — `_base_context()` — common template vars
- `app/database.py:1118` — `get_dashboard_stats_range()` with comparison period
- `app/templates/base.html` — sidebar, mobile header, theme toggle JS, flatpickr init
- `app/templates/dashboard.html` — main dashboard, greeting, stats, chart, recent docs
- `app/static/css/style.css` — single CSS file, versioned `?v=14`
- `app/static/css/style.css:1487` — dashboard greeting/comparison stat styles
- `app/static/css/style.css:1556` — mobile card improvements (`.mobile-cards tbody tr` card layout)
- `app/static/css/style.css:1581` — `.dash-recent-mobile` compact list

## Working notes
- **Git branch:** Work on `claude/<session-id>` branches (system blocks pushes to non-`claude/*` branches with 403). User pushes to main manually.
- **Test before reporting done:** Use `from app.main import app; from fastapi.testclient import TestClient` to smoke-test pages
- **Login flow for testing:** Fresh DB creates admin with printed password; first login requires `/set-password` then `/setup`
- **Latvian language only** — all user-facing strings are in Latvian. Don't add English.
- **Premium = restraint:** When in doubt, remove decoration. The user explicitly rejected colorful "AI default" looks. Stick to near-monochrome.
- **Mobile-first:** User's primary feedback is mobile UX. Always test mobile viewport (≤768px).
- **No new deps without asking** — keep the dependency footprint small.
