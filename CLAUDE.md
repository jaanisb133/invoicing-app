# V-Rēķini — Project Context

Latvian invoicing SaaS built with FastAPI + Jinja2 + SQLite. The user is
building this as a portfolio piece, so it needs to be **impressive both
visually and functionally** — a near-monochrome premium aesthetic with
genuinely modern UX patterns, not generic "AI dashboard" defaults.

## Stack
- **Backend:** FastAPI (`app/main.py`), SQLite (`app/database.py`), ReportLab for PDFs (`app/pdf_generator.py`)
- **Templates:** Jinja2, located in `app/templates/`
- **Frontend:** Vanilla JS, Chart.js 4.4.4, flatpickr for date pickers
- **Styling:** `app/static/css/app.css` for every signed-in screen (loaded by `base.html`);
  `app/static/css/site.css` for the landing page and 404 (same tokens, public composition);
  `app/static/css/style.css` still serves pricing/login/register/contacts/terms in the old look.
  All versioned through `CSS_VERSION` (see Gotchas)
- **Number format:** `app/fmt.py` — `eur` / `num` / `qty` Jinja filters and JS `fmtEur` /
  `fmtNum` / `fmtQty` / `parseNum` / `fmtDate` in `base.html`
- **Fonts:** Geist (app UI) + DM Sans (paper previews, public pages) from Google Fonts, with system fallbacks

## Architecture notes
- Multi-tenant SaaS — all business data isolated per `user_id`
- Tier-gated features (free/mini/starter/business/admin) via `tier_limits` dict
- `_base_context()` provides common template vars: `current_user`, `tier`, `tier_label`, `tier_limits`, `stock_enabled`, `needs_setup`, `offline_mode`
- Dashboard stats API: `/api/dashboard-stats?date_from=&date_to=` returns JSON used for AJAX refresh on date-range changes
- Document table query (`db.get_documents()`) returns `total_with_vat` computed via SQL subquery

## Design system — "achromatic ledger" (redesign approved 2026-10-21)

Dealt by design-taste-frontend `--app` (sheet A, seed 1740845365) and built in
`app.css`. The old near-monochrome-on-white and the later blue (`--brand #3B82F6`)
are both gone. **Colour lives on data, never on chrome.**

### Tokens (`:root` in `app.css`; dark under `:root[data-theme="dark"]`)
- Ground `--ground #f2f4f7` (blue-grey), panels `--surface #fff`, ink `--text #0a0a0a`,
  secondary `--muted #616468`, labels `--faint #66696d` (≥ 4.5:1 on the ground — don't lighten)
- `--primary #141414` — the one near-black primary button per screen
- `--data #1d5fbf` — the only hue: chart bars, the due-strip "today" marker
- Status: `--positive #2e7d32`, `--negative #c4242a`, plus `--pill-*-bg/-ink` pairs
- Old names (`--brand`, `--text-light`, `--bg-card`, …) are aliased to the new tokens so
  untouched templates keep working; use the new names in new code
- Font Geist (UI) + DM Sans (paper previews); radii 8 / 6 / 4

### Rules (taste-skill `references/app-screens.md`)
- Flat: 1px borders, no resting shadows. Only real overlays (menus, dialogs, flatpickr,
  comboboxes) may float with `--float-shadow`. Selected segments use a 1px inset outline
- KPIs are type in one divided strip (`.kpi-strip`) — no sparklines, icon tiles or count-up
- Noun titles in `<h1>` (`.page-header h1` + `.page-sub`), at most one primary button
- Tables: right-aligned tabular figures. Phones: two-line rows (identity + amount, then
  grey meta + status). Mind desktop `width: N%` on cells leaking into the mobile grid
- Every screen states its one finding (dashboard: "3 rēķini kavēti par …")
- No entrance motion. Paper previews (`#invoicePreview`, `#docPreview`) are white in
  both themes and carry `data-ui`: they mirror the PDF at scale, so their 7–10px text is
  deliberate
- Latvian formats everywhere: `1 955,84 €` (NBSP thousands, comma decimals), `dd.mm.yyyy`
- Verify with `node .claude/skills/design-taste-frontend/scripts/inspect.mjs --app` on a
  rendered snapshot; defensible remaining findings: paper-preview tiny text, short lists
  leaving empty ground, flatpickr calendars when its CDN is blocked

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
- ⛔ **Sparklines, stat count-up, chart entrance animation** — built, then removed in the
  2026-10-21 redesign (taste-skill app rules: KPIs as type, no entrance motion). The API
  still returns `spark_*` arrays; nothing reads them.
- ✅ **Empty states with personality** — `_empty_state.html` macro (mark + title +
  one line + CTA), used on dashboard, documents, clients, products, offers, stock.
  `/documents` distinguishes "no documents yet" from "no match for these filters"
  (the latter offers "Notīrīt filtrus").
- ✅ **Loading states** — flat skeletons on the KPI values and a dimmed chart while the
  date-range fetch is in flight.
- ✅ **Focus and press** — keyboard focus rings, press feedback on controls.
- ✅ **Bottom nav on mobile** and **PWA manifest** — already shipped earlier.

- ✅ **Chart granularity** — Dienas / Nedēļas / Mēneši toggle on the revenue chart.
  `buildChartSeries()` in `dashboard.html` buckets the sparse per-day API data into
  gap-free day/week/month series (weeks start Monday, buckets clip to the range so
  totals are identical at every granularity). `_chartGrain` is 'auto' until the user
  picks one: day ≤ 62 days, week ≤ 366, month beyond. Choice persists in localStorage.
- ✅ **Redesign (2026-10-21)** — new shell (labelled sidebar on the ground, account menu
  with theme toggle, mobile bottom nav with a + button, `N` shortcut for a new invoice).
  Invoice editor: client combobox (recent first, inline create), payment-term chips,
  spreadsheet lines (Enter walks name → qty → unit → price → new row, Ctrl/⌘+Enter
  submits), product picker that fills unit and last price, live paper preview. Dashboard:
  KPI strip with "pret dd.mm.–dd.mm." deltas, Termiņi due strip, activity. Lists:
  status tabs, search, last-invoice / last-price columns. Server `_parse_doc_items()`
  reads the line indices actually posted (deleting a middle line used to drop the rest)
  and accepts `1 234,50`.
- ✅ **Offer accepted/rejected state** — offers have gaida atbildi / pieņemts / noraidīts.
- ✅ **Offer → invoice** — "Izveidot rēķinu" on an offer opens a prefilled invoice
  form (client, items, VAT, notes, `included_in_price` flags). Nothing is saved until
  submit, and the offer is never modified. `documents.converted_from_offer_id` records
  the link: the offer shows which invoice it produced, the invoice links back, the
  offers list badges converted offers, and a second conversion asks for confirmation.
  A forged `from_offer` pointing at another user's document is ignored.

### Public site — landing (`landing.html` + `site.css`, 2026-10-21)
Dealt by design-taste-frontend (direction `split-stage`, seed 1015495166, palette/type kept
from the app). Idea: a real Latvian invoice stays pinned while the page reads, and fills in.
- **Live thing:** typing a company searches `/api/registry/search` (public, rate-limited)
  and sets the supplier; qty/price, VAT (21/12/apgrieztā/bez PVN), template and PDF↔PEPPOL
  XML controls re-render the pinned invoice. On phones the pin is a 172px strip cropped to
  the part being changed (taller sticky panels fail the inspector's covered-text check).
- **The sign-up dialog** carries the chosen company into `/register?display_name=&reg_number=
  &legal_address=&entity_type=` — `register_page()` accepts these as prefill.
- **Footage:** `app/static/media/editor{,-phone}.mp4` are real, not-sped-up recordings of
  the editor ("Bez paātrinājuma" claims it). Regenerate after editor UI changes with
  `scripts/footage/seed.py` + `scripts/footage/record.py` (fictional SIA "Ziemeļu Apdare").
- **Sample content** (client "Bērzu Darbnīca", due list, export rows) is fictional; dates are
  relative to today via the `day(n)` helper so "kavēts 4 d." stays true. Prices come from
  `TIER_LIMITS`; FAQ items are one Jinja list rendered as text and as FAQPage JSON-LD.
- `app/static/og-image.png` is a 1200×630 render of the hero; re-render if the hero changes.

### SEO state (2026-10-21)
- Indexable: `/`, `/pricing`, `/contacts`, `/terms` — listed in `SITEMAP_PAGES` with real
  lastmod dates (update the date when a page's content changes). `/login`, `/register` are
  crawlable but `noindex` (robots.txt must not block them, or the noindex is never read).
- Unknown URLs return a real 404 (`404.html`); guests used to be 303'd to /login (soft 404).
- `HeadAndSecurityHeaders` middleware: HEAD works on every GET route; nosniff, Referrer-Policy,
  X-Frame-Options SAMEORIGIN, Permissions-Policy; HSTS only over HTTPS. No CSP yet (inline
  scripts everywhere — needs nonces first).

### Still open
1. **Pricing / login / register / contacts / terms** still on `style.css` (old blue look) —
   restyle onto `site.css` so the path from the landing page stays in one design.
2. **List actions on mobile** — swipe for mark-paid/delete
3. **Per-line rounding** — totals are computed unrounded (line = q×p, VAT on the sum);
   the preview mirrors the server exactly, but a printed line can differ by a cent from
   its rounded parts. Pre-existing accounting behaviour; change only deliberately
4. **Self-host the footer payment logos** — `_public_footer.html` hotlinks all Visa /
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
- **Cards that aren't range-scoped must say so.** "Neapmaksāti, visi" is all-time
  outstanding by design, sitting in a strip of range-scoped stats.
- **`requestSubmit()` ignores disabled buttons.** Ctrl/⌘+Enter on the invoice form goes
  through it, so the submit handler re-checks the stock error itself.
- **Stock mode makes the unit cell read-only** (it comes from the product), so Enter
  skips it — keyboard tests must branch on that.
- **`[hidden]` is `display:none !important`** in `app.css`; component display rules
  used to override the attribute.

## Critical files to know
- `app/main.py` — `_base_context()`, `_parse_doc_items()`, `_doc_list_rows()`,
  `dashboard()`, `/api/dashboard-stats` (grep the names; line numbers drift)
- `app/database.py` — `get_dashboard_stats_range()` (comparison period),
  `get_product_last_prices()`, `get_client_last_billed()`, `get_unpaid_invoices()`
- `app/fmt.py` — Latvian number formatting and parsing
- `app/templates/base.html` — shell, theme init, JS format helpers, flatpickr init
- `app/templates/document_form.html` — invoice/offer editor (combobox, rows, preview)
- `app/templates/dashboard.html` + `_dash_activity.html` — dashboard
- `app/static/css/app.css` — the app stylesheet; tokens at the top

## Working notes
- **Git branch:** Work on `claude/<session-id>` branches (system blocks pushes to non-`claude/*` branches with 403). User pushes to main manually.
- **Test before reporting done:** Use `from app.main import app; from fastapi.testclient import TestClient` to smoke-test pages
- **Login flow for testing:** Fresh DB creates admin with printed password; first login requires `/set-password` then `/setup`
- **Latvian language only** — all user-facing strings are in Latvian. Don't add English.
  Reverse charge prints as "nodokļa apgrieztā maksāšana" (PVN likums wording), not "Reverse Charge".
- **Premium = restraint:** When in doubt, remove decoration. The user explicitly rejected colorful "AI default" looks. Chrome stays achromatic; `--data` blue is for data only.
- **Mobile-first:** User's primary feedback is mobile UX. Always test mobile viewport (≤768px).
- **No new deps without asking** — keep the dependency footprint small.

## Vendored skills (`.claude/skills/`, `.claude/agents/`)
Committed to the repo because cloud sessions never install plugins; sources,
versions and local patches are in `.claude/skills/VENDORED.md`.
- **design-taste-frontend** (taste-skill v2) — the main design skill. The user
  approved a full redesign driven by it (2026-10-21), colours included, so its
  directions may replace tokens. The app now runs on its sheet (see Design system). App screens use its `--app` mode
  (`references/app-screens.md`). In cloud sessions run its scripts with
  `CHROME_PATH=/opt/pw-browsers/chromium`; working files go to `.taste-skill/` (gitignored).
- **high-end-visual-design** — opt-in classic (marketing-site look: big whitespace,
  scroll reveals, pill CTAs). Model invocation is disabled upstream, so read its
  `SKILL.md` directly. Fits the public landing page; too slow and airy for work
  screens like the invoice form, where design-taste-frontend's app rules win.
- **claude-seo** (`seo`, `seo-*` + 19 agents) — for the public pages (landing,
  pricing, legal). The app is server-rendered Jinja, so rendered-page (Chromium)
  features aren't needed; its runtime runs fine without them. First use in a session
  runs `.claude/skills/seo/scripts/claude-seo setup` (~3 min, venv is gitignored).
  `seo-dataforseo`, `seo-image-gen`, `seo-google` and parts of `seo-maps` need API keys
  or Google credentials we don't have — skip them unless the user provides them.
