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

- ✅ **Chart granularity** — Dienas / Nedēļas / Mēneši toggle on the revenue chart.
  `buildChartSeries()` in `dashboard.html` buckets the sparse per-day API data into
  gap-free day/week/month series (weeks start Monday, buckets clip to the range so
  totals are identical at every granularity). `_chartGrain` is 'auto' until the user
  picks one: day ≤ 62 days, week ≤ 366, month beyond. Choice persists in localStorage.
- ✅ **Offer → invoice** — "Izveidot rēķinu" on an offer opens a prefilled invoice
  form (client, items, VAT, notes, `included_in_price` flags). Nothing is saved until
  submit, and the offer is never modified. `documents.converted_from_offer_id` records
  the link: the offer shows which invoice it produced, the invoice links back, the
  offers list badges converted offers, and a second conversion asks for confirmation.
  A forged `from_offer` pointing at another user's document is ignored.

### Still open
1. **Offer accepted/rejected state** — offers have no lifecycle. "Has an invoice" is
   the only signal of a won deal; there is no way to mark one rejected or expired,
   so the list can't be triaged. Biggest remaining gap in the offers feature.
2. **Hero stat treatment** — make the primary revenue card more visually dominant on mobile
3. **List redesign on mobile** — swipe actions for mark-paid/delete; sticky filter bar (FAB already exists)
4. **Dashboard "alive" feel** — upcoming due dates highlighted, "X days since last invoice" prompts
5. **Self-host the footer payment logos** — `_public_footer.html` hotlinks all Visa /
   Mastercard / Google Pay / Apple Pay / EveryPay / bank logos from
   `vnmedia.lv/wp-content/uploads/2026/03/...`. A WordPress media reshuffle silently
   breaks the card logos SEB compliance requires, on every public page.

### Branded tāmes (custom offer PDF design, per-account)
Built for the TT Konstrukcijas client: a premium dark/gold offer PDF
replicating their mockup (diagonal header with logo + photo + contacts, spec
and priekšrocības boxes with drawn line icons, product table, totals band,
conditions strip, photo row). Architecture is three layers:
- **Template** (`app/pdf_branded.py`) — hardcoded layout/colors, drawn on the
  raw ReportLab canvas with manual pagination; every section measures itself,
  so free-form text lengths page-break gracefully. Icons are drawn as stroke
  primitives (`_icon()`), keyword-matched from labels. Brand assets live in
  `app/custom_assets/tt/`. Photos embed as JPEG + white corner patches
  (`_round_corners`) — never PNG w/ alpha, that ballooned the PDF to 5MB.
- **Presets** ("Tāmju veidnes", `/tames`) — per-account rows in
  `offer_presets` (title, spec rows, benefit rows, conditions, up to 5 photos
  in `data/preset_photos/{uid}_*`). Client duplicates + edits text per
  product. First visit seeds a full example preset from the bundled assets.
- **Per-offer copy** — picking a preset on the offer form copies its content
  into `documents.offer_meta` (JSON); later preset edits never rewrite sent
  offers. `offer_branded` hidden field: absent=keep, "0"=clear, "1"=save.
Gated by user setting `branded_offers` ("Tāmju dizains" toggle on the admin
/users page); not tier-tied. `_generate_doc_pdf()` in main.py routes offer
PDFs (download/send/create/update) to the branded generator when meta is
present. Header contacts come from settings keys `company_phone`,
`company_website`, `offer_tagline` (fields show on /settings when enabled).
Branded form JS is a separate `<script>` block in document_form.html so it
can't kill the main form logic.

## Gotchas worth remembering
- **`dashboard.html` is one ~490-line `<script>` block.** An uncaught error anywhere
  in it kills every feature below — this already happened once when Chart.js failed to
  load and took the date presets, AJAX refresh and sparklines with it. Chart and
  flatpickr init are now guarded; keep new top-level code defensive.
- **CSS version lives in one place:** `CSS_VERSION` in `main.py`, exposed as the
  `css_version` Jinja global. Bump it on every CSS change. Do not hardcode `?v=N` in a
  template — nine standalone templates used to and had drifted to v18 while base.html
  was on v21, so landing/login/register/pricing served visitors a stale stylesheet.
- **Cards that aren't range-scoped must say so.** "Neapmaksāti (kopā)" is all-time
  outstanding by design, sitting in a row of range-scoped stats.
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
