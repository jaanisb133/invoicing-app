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
  `app/static/css/site.css` for every public page: landing, pricing, login, register, setup,
  guides, contacts, terms, license, set-password, 404 (same tokens, public composition;
  `auth_base.html` for forms, `_site_*.html` partials for the rest). The old `style.css`
  is gone. All versioned through `CSS_VERSION` (see Gotchas)
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
  Invoice editor: client combobox (recent first, inline create, and below the account's
  clients the matching Uzņēmumu reģistrs companies: a pick calls `POST /api/clients/from-registry`,
  which takes name/address from our registry copy (`registry.get`), returns an existing client
  with that reg. no. instead of a duplicate, respects the client limit, and fills the VAT number
  only when VIES confirms it (`_vies_check`: None = no answer, never read as "not a payer");
  a registry match already saved shows as that client, "jau klients"), payment-term chips,
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
- **Light only.** The public site ignores the in-app theme and the OS dark mode (owner's call,
  2026-10-21): `site.css` has no dark tokens and the pages set no `data-theme`.
- **Footage:** `app/static/media/editor{,-phone}.mp4` are real, not-sped-up recordings of
  the editor ("Bez paātrinājuma" claims it). Regenerate after editor UI changes with
  `scripts/footage/seed.py` + `scripts/footage/record.py` (fictional photo studio SIA "Ziemeļu
  Kadrs"; pass `--vendor` with local flatpickr/Chart.js where jsdelivr is blocked, or the
  date fields record in the browser's US format). The sample lines (product photos, image
  editing) are deliberately not construction: facade painting between two VAT payers is
  reverse charge, so a 21 % sample would teach the wrong thing.
- **Sample content** (client "Bērzu Darbnīca", due list, export rows) is fictional; dates are
  relative to today via the `day(n)` helper so "kavēts 4 d." stays true. Prices come from
  `TIER_LIMITS`; FAQ items are one Jinja list rendered as text and as FAQPage JSON-LD.
- `app/static/og-image.png` is a 1200×630 render of the hero; re-render if the hero changes.
- **Portfolio screenshots** (`docs/screenshots/vnmedia/`, used on vnmedia.lv/projekti/v-rekini):
  `scripts/footage/showcase.py` seeds a lived-in fictional account (invoices since January last
  year, created in date order so numbers run with dates; overdue, credit note, offers, recurring),
  `scripts/footage/screens.py` captures desktop/phone × dark/light, the landing and the three PDF
  designs. See the folder's README; re-shoot after visible UI changes.

### SEO state (2026-10-21)
- Indexable: `/`, `/pricing`, `/contacts`, `/terms` — listed in `SITEMAP_PAGES` with real
  lastmod dates (update the date when a page's content changes) — plus `/celvedis` and every
  published guide, which the sitemap adds from `GUIDES` (lastmod = `updated`). `/login`, `/register` are
  crawlable but `noindex` (robots.txt must not block them, or the noindex is never read).
- Unknown URLs return a real 404 (`404.html`); guests used to be 303'd to /login (soft 404).
- `HeadAndSecurityHeaders` middleware: HEAD works on every GET route; nosniff, Referrer-Policy,
  X-Frame-Options SAMEORIGIN, Permissions-Policy; HSTS only over HTTPS. No CSP yet (inline
  scripts everywhere — needs nonces first).

### Plans, trial and paywalls (2026-10-21)
- `TIER_LIMITS` is the single source: free = 5 invoices/month, 25 clients, unlimited products,
  5 e-mails, all templates; Mini 50/50; nothing caps products. Pricing pages, the landing
  page and gates render from it (`plans` Jinja global). `LIFETIME_CAP` = 10.
- Prices (2026-10-21): Mini 2,00 € (was 1,99 €, which 21 % VAT can't split into cents), Pamata 4,99 €,
  Bizness 9,99 €; yearly = ten months
  ("2 mēn. bez maksas"); lifetime 199 €. Set against Numbero (free 1 doc, 2 € / 6 docs,
  6 € / 100, 10 € unlimited): Mini matches their 2 € with 50 invoices; the rest cost less. Renewals read the
  current price, so a change applies to existing subscribers at their next charge.
- A locked feature names the plan that unlocks it (`plans.<tier>.label`), never "PRO".
- **Trial:** every new account gets 14 days of Pamata (`trial_until` user setting on the
  account). `_apply_trial()` in `_with_account` sets `user["tier"]` (effective, what gates
  read) and keeps `user["plan_tier"]` (what was paid for; billing/pricing screens compare
  this). Free accounts without a trial can start it once (`POST /trial/start`, offered on
  gates the trial would unlock). Renewal reads raw rows, so trials are never charged.
- Free-plan PDFs and previews print "Sagatavots ar V-Rēķini · v-rekini.lv" (`_plan_footer`).
- The monthly invoice limit is shown on `/documents/new` before the editor (`doc_limit.html`);
  free users can send e-mail (`_email_enabled`). `_plan_note.html` warns at ≤ 2 invoices left
  and in a trial's last 5 days.

### Sign-up and first run (2026-10-21)
- Every sign-up e-mails the owner (`NEW_ACCOUNT_NOTIFY_EMAIL`, default janis@vnmedia.lv;
  empty turns it off) after the response, so a slow mail server never holds up sign-up.
- "Ienākt" is a real button: beside "Sākt bez maksas" in the landing hero (owner moved it
  there from the pinned invoice's corner), and top-right in `_site_bar.html` / the pricing header.
- Register: company via registry search (or name for a person), e-mail, one password with
  show/hide. Picked plan (`?plan=mini|starter|business|lifetime`) carries through setup to
  checkout. Setup is one screen; payment term defaults to 14 days.
- Dashboard "Pirmie soļi" (`_first_steps.html`, `get_onboarding_state`) until done or hidden.
- **Sign-up funnel** (admin: `/users/registracijas`, tab beside Lietotāji): each load of /register
  is one attempt, named by a random id in a hidden field `su` (no cookie, no IP, no typed
  values). The page beacons steps to `POST /api/signup-step` (open + source, start, focus,
  company/email/password filled, click, invalid); `POST /register` logs submit, error codes
  and `created` (with user_id); setup / first invoice / sent come from the account. Table
  `signup_steps`, rows older than 400 days purged. Milestones are counted in order, fields
  on their own; "where they stopped" = last field clicked into and left unfinished. Bots and
  headless browsers are ignored by user agent, so Playwright tests must set a normal UA.
  A re-shown form (POST error) continues the attempt and reports no second `open`.
  Mentioned in the terms (§ 9).
- **Bots** (2026-10-25, after a script made "rz7867 z2of9e"): /register has a honeypot field
  `website` (off screen, `tabindex=-1`) and a signed stamp `ft` (`_signup_form_token`, salt
  "signup-form"): no stamp, another attempt's stamp, under `SIGNUP_MIN_SECONDS` (3, stamp is
  whole seconds so 2–3 s) or a filled trap → the same plain "pārbaudiet datus" re-render, logged
  `bot_token` / `too_fast` / `bot_trap` (`SIGNUP_BOT_ERRORS`, left out of the funnel and counted
  as "Robotu mēģinājumi atturēti"). A stamp over a day old is a person: "Lapa bija atvērta
  pārāk ilgi". A person's name must be letters (`_PERSON_NAME`, NFC first; JS mirrors it);
  e-mail is checked and stored lower case; `get_user_by_email` ignores case. Tests that POST
  /register must send `su` + `ft` (`m._signup_form_token(su)`) and set `m.SIGNUP_MIN_SECONDS = 0`.
- **E-mail verification** (`users.email_verified` = the proved address, lower case): the app
  sends e-mail for an account (send route, recurring) only when `_can_send_email` — the owner's
  current address equals it, or the owner is admin, or offline. The link (`/verify-email`,
  public, 14 days, salt "verify-email") goes out after `/setup` (once, `_verify_sent`), on an
  owner's address change and from "Sūtīt saiti vēlreiz" (`POST /verify-email/send`, 3/h, answers
  `?verify=sent|wait|failed|done` in a dialog in `base.html`). A password reset and an admin-made
  account count as proved. Migration trusted accounts that had finished setup; bare sign-ups get
  the link at setup. Notes: `_plan_note.html` (dashboard, editor), `_verify_note.html` inside
  every send dialog (Nosūtīt disabled), Mans konts, recurring forms; `/users` flags set-up
  accounts with "e-pasts nav apstiprināts". Trial and free accounts also send ≤ 20 e-mails an
  hour (`send:{account}` in the in-memory limiter).
- Guided tours: page sets `window.VR_TOUR` in `{% block tour %}`; engine in `base.html`;
  seen keys per person in user setting `tours_seen` (`POST /api/tour-seen`). Tours:
  `dashboard`, `editor`. Help page `/palidziba` (`help.html`).

### Guides (`/celvedis`, all five published 2026-10-21)
- `app/guides.py` (`GUIDES` list) + body files `app/templates/guides/<slug>.html`, rendered by
  `guide.html`. `published: False` → reachable by URL, `noindex`, not in the sitemap or menus.
  `/celvedis` lists the drafts (tagged "Melnraksts", `noindex`) while none is published;
  after that guests see published guides and the admin also sees drafts.
  Publishing = set True and `published_on` to the day (Article `datePublished`); a later
  content change bumps `updated` only. Sitemap and `/celvedis` pick it up.
- Linked from the public top bar ("Ceļvedis", desktop), every public footer, and two landing
  FAQ answers (`faq_more` in `landing.html`; the FAQPage JSON-LD stays plain text). Each guide
  lists three others under "Vēl ceļvedī".
- `/static/guides/rekina-paraugs.pdf` is a real app PDF of the article's sample invoice
  (`scripts/footage/sample_pdf.py` on the footage account; change article and PDF together).
  The script also renders `rekina-paraugs.png` (pdftoppm), the thumbnail in the download
  block that opens the article: any guide with `static/guides/<slug>.pdf` gets that block
  (`sample_title` / `sample_pages` / `sample_alt` in `GUIDES`).
- Line tables in articles fit a 360 px phone (tight cells ≤ 520px); under that they scroll.
- Checked against the law texts on likumi.lv on 2026-10-21 (PVN likums 41–43, 59, 125–133,
  141–143.⁴; Grāmatvedības likums 3, 6, 11, 28 + pārejas noteikumi 8–10; MK 749; MK 322;
  e-address and e-documents laws). Claims only VID made were removed or reworded onto the
  law: vid.gov.lv and fm.gov.lv reset the connection from cloud sessions even when allowed.
  `sources` lists only what was read. A new claim gets a `<!-- PĀRBAUDĪT: … -->` comment
  until checked.
  Drafts render them as visible "Pārbaudīt:" boxes (`guide_checks` filter); published pages
  strip any left over.

### Still open
1. **Last payment logos** — all marks are official files from the owner, committed in
   `app/static/img/payments/` (see SOURCES.txt). EveryPay is still missing and prints as
   text; Mastercard's supplied PNG is tiny (74×52) and soft on the terms page — swap in an
   SVG when the owner has one. Logo presence is read at startup: restart after adding files.
2. **VID filing** — not built. Researched in `E-INVOICING.md` (law, VID behaviour, the
   90-day EDS credential, the e-adrese route). Steps 1–2 of its build order are done (below).

### Money and the life of an invoice (2026-10-21)
- **One rounding rule** (`app/money.py`, JS twin `vrLine` / `vrTotals` / `vrRound2` in
  `base.html`): each line rounded to the cent half-up on the decimal value, VAT once on the
  sum of rounded lines. It is what EN 16931 checks, so PDF, previews, lists, dashboard and
  XML agree to the cent. Never compute a total from `quantity * price` anywhere else.
- **Totals are stored**: `documents.subtotal / vat_amount / rounding / total`, written on
  every create/update; `document_items.total` is the rounded line. Documents saved before
  this were backfilled with the totals they always printed (old arithmetic), so nothing
  issued moved by a cent. Readers use the stored values (`pdf_generator.document_amounts`).
- `rounding` (BT-114) exists only for subscription invoices whose price can't be split: 1,99 € at 21 % has no
  two-decimal net, so `money.net_for_gross` gives 1,64 + 0,34 + 0,01 rounding.
- Unit prices print with their real decimals (`fmt.price` / `fmtPrice`): 0,0145, not 0,01.
- **Buyer reference** (EN 16931 BT-10, `documents.buyer_reference`): the code the buyer
  routes on (a council's school "09.283", an order number). Optional field under the client
  in the editor, prefilled from `clients.buyer_reference`; printed "Atsauce: …" in the buyer
  block; sent as `BuyerReference` (else the buyer's reg. no.). Recurring invoices take the
  client's; credit notes and corrections copy the original's.
- An invoice with no due date gets the payment term "Apmaksas termiņš nav noteikts" in the
  XML: an amount due needs a due date or terms (BR-CO-25).
- **Sent = locked** (`documents.sent_at`, `db.is_locked`): set when a sales invoice or
  credit note is e-mailed from the app, marked paid, or the user presses "Atzīmēt kā
  nosūtītu". Not on download. Locked documents can't be edited, deleted, trashed or purged
  (server-side in `update_document` / `delete_document`; UI hides the actions). First
  migration locked everything already e-mailed or paid.
- **Fixing a sent invoice** (MK 877 p.25.1): `doc_type='credit'` credit notes (own series,
  prefix `credit_doc_prefix`, default "KR"; positive amounts, subtracted in revenue at their
  own date) and corrective invoices (`doc_type='sell'` with `ref_doc_id`). Both point at the
  original via `ref_doc_id`; the original's status becomes `cancelled` (fully credited) or
  `replaced` (corrected) through `db.refresh_original_status`, called after every
  create/update/delete/restore of a follow-up. "Anulēt" = `POST /documents/{id}/cancel`
  (full credit note); "Koriģēt" = `/documents/new?corrects=`; partial = `?credits=`.
  Same client as the original, enforced on the server; never blocked by the monthly limit.
- Revenue SQL lives in `database.REVENUE_SQL` / `INVOICE_SQL`: credit notes subtract, a
  replaced invoice drops out (its correction carries the sale). Status values for sales:
  `issued` (awaiting payment), `paid`, `cancelled`, `replaced`.
- **E-invoice XML** (`app/einvoice.py`): Invoice 380 (corrective = 380 + BillingReference;
  384 is German-only), CreditNote 381; category O for non-VAT payers, AE for reverse charge,
  endpoints 0218 (LV reg. no.) / country VAT schemes. `problems(doc_id)` lists what the
  user must fill in; the document page shows it. Validated against PEPPOL BIS 3.0 + EN 16931
  Schematron and the UBL 2.1 XSD in 13 scenarios; to re-run, fetch the rules from
  github.com/OpenPEPPOL/peppol-bis-invoice-3 (`rules/sch`), compile with the ISO Schematron
  XSLT2 skeleton and run with saxonche in a scratch venv (not an app dependency).

### Invoice PDFs (redesigned 2026-10-21)
- `app/pdf_generator.py`: three templates built from shared parts (`_head_*`, `_parties`,
  `_lines`, `_summary` = payment details + totals, `_notes`, `_sign_off`, page `_chrome`),
  geometry/type per template in `THEMES`. classic = serif title over a double rule in the
  accent; modern = the amount due in an accent panel (`_Panel`, drawn on the canvas);
  minimal = hairlines, a 3-column party row, an accent marker.
- Every page: footer with the supplier's name and contacts (`company_email`, `company_phone`,
  `company_website`, now on /settings for everyone) and "1 / n" (`_numbered_canvas`); a
  running header from page 2; the free-plan line. Line header repeats across pages.
- Fonts in `app/fonts` (OFL): DM Sans 400/500/600/700/italic, Source Serif 4 400/600/italic.
  `_register_fonts()` still returns the regular/bold pair `pdf_branded` uses.
- User text goes through `_x()` (escaped; an "&" used to break the PDF); names and
  addresses through `_xq()`, which prints straight quotes as „…”. Not line items (27" = inches).
- Payment details (bank, IBAN in fours, "Maksājuma mērķis") only on sales invoices with an
  account. Persons print "P. k.", companies "Reģ. Nr." (`client_type` / `entity_type`).
- **The previews are the same layout in HTML:** `static/js/paper.js` (`vrPaper.render`) draws
  an A4 page 595 px wide (1 pt = 1 px) and scales it; CSS is the `.pp` block at the end of
  `app.css`, with the PDF's numbers. Editor (`#invoicePreview`, modal) and document page use
  it. A change to one side needs the other; compare a PDF at 72 dpi with the preview at
  595 px side by side.
- The landing's pinned invoice (`site.css` `[data-ui].paper.t-*`) is a reading-size cousin,
  not a mirror; keep its template variants in the same spirit.
- Test against the pinned ReportLab (4.2.2), not whatever a venv has.

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
- **Numbering never reuses a sent number.** Type 2 (daily) numbering counts from the day's
  highest `seq_num`, not the number of documents: with a count, deleting the 2nd of three
  made the next one a second "03".
- **Icons:** `scripts/icons.py` draws every icon from the receipt mark (PWA tiles, apple-touch,
  favicon SVG/PNG/ICO; 16 px has its own pixel-grid drawing). Every `<head>` includes
  `_icons.html` — the only place icon links live. Browsers cache favicons by URL, so after a
  change bump its `?v=` (and the manifest's). The old blue "VR" lingered for exactly this reason.
  `/favicon.ico` is a real route (Bing and feed readers ask for it).
- **The service worker is cache-first for `/static/`** (`static/sw.js`) and never revalidates:
  a changed file only reaches app users under a new URL (`?v=`) or after `CACHE` is bumped.
- **Payments** (security review 2026-10-23). `/everypay/callback` is public and answers GET
  and POST: it looks up the order and its stored `_pending_payment_ref` *before* asking
  EveryPay anything, then `_payment_matches_order` requires EveryPay's own `order_reference`
  and an amount equal to the plan's current price; the order is then closed (`_clear_pending`)
  so a replay does nothing. `/billing/return` runs the same check and acts on `account_id`.
  Before this, a settled 2 € payment named beside an unpaid lifetime order bought the licence.
  Cancel stops renewal (token forgotten) and keeps the plan to `subscription_end`
  (`cancel_at_period_end`; `_apply_trial` and the daily `expire_cancelled_subscriptions` make
  it free after); lifetime can't be cancelled. A renewal charge that times out is looked up
  (`charge_mit`), never retried blind.
- **Plan changes are prorated** (`_unused_credit`, `_plan_quote` before `/billing/checkout`):
  the unused part of a card-paid period is credited. `due = price − credit`; ≥ 1 € (always for
  lifetime) is charged and starts a full period today; below that the plan switches with no
  payment (`db.change_plan`) and the credit buys `floor(credit ÷ daily price)` days. Every
  period records `_period_value` / `_period_start` (`_start_period`: activation, renewal,
  switch), so credit is value × days left ÷ length: exact, never more than was paid, and
  floors mean switching back and forth can't gain. Checkout stores `_pending_amount`, which
  is what EveryPay must say was paid. Trials and admin-set plans (no payment ref) earn none.
  The pricing page shows each change's cost today (`quotes`), incl. the current plan's other cycle.
- **Tenancy: every id from a form is checked.** `db.client_belongs` / `db.own_items` on document
  and recurring forms; `get_client(id, account_id)` / `get_product(id, account_id)` on every
  read for a document (pass `doc["user_id"]`), and `get_document` joins products by account.
  A foreign client already on a row shows as blank (`defaultdict(str)` in the view).
- **Trashed documents are only restored or purged:** every other document route 404s on
  `deleted_at`. The monthly limit counts documents *made* (rows incl. trashed, and the
  `_docs_made_month` counter that survives purge). Corrective invoices and credit notes start
  only from a sent invoice (`_followup_source`), which is also what the UI offers.
- **Recurring:** a first run in the past is clamped to today; the scheduler moves `next_run`
  past today in one step, runs only the plan's `max_recurring` oldest schedules, respects the
  monthly e-mail cap and skips schedules whose client isn't the account's.
- **Seats:** `db.member_within_seats` in `_get_current_user` and at login: after a downgrade
  only the oldest members that fit the plan can work.
- **PDF files** are `data/dokumenti/{account}/{document}/{number}.pdf` (`document_pdf_path`):
  one shared `{number}.pdf` served other accounts' invoices under concurrent downloads.
- **Sessions** sign `{u: id, h: password-hash tail}`: a password change ends every other
  session (the changing one is re-issued). Cookies get `Secure` from `HeadAndSecurityHeaders`
  over HTTPS. The 2026-10-23 deploy logged everyone out once (old cookies were a bare id).
- Redirect targets from requests go through `_local_path`; `return_to` on send likewise.
  Profile e-mail must be unique; logo uploads must be a real image ≤ 5 MB.
- **Phone lists act by swipe** (`static/js/swipe.js`): the ⋯ menu is hidden ≤ 768px, so rows
  carry `data-swipe` and the page passes their actions to `vrSwipe.attach`. Delete and
  restore answer JSON when asked (`Accept: application/json`) so the swipe can offer undo.
  Rows need `touch-action: pan-y`, or the browser takes the horizontal drag.

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
  Reverse charge prints as "nodokļa apgrieztā maksāšana" (PVN likums wording), not "Reverse Charge",
  and in place of the VAT rate and amount (shown as "—"): never "PVN 0 %", which is a different
  rate. The e-invoice keeps category AE with 0 % because PEPPOL requires it.
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
