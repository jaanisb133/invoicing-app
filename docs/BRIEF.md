# V-Rēķini — product brief

A reference document for writing copy and generating visuals. Written in
English so it works with any tool; the product itself is **Latvian-only** and
all customer-facing copy must be in Latvian.

Everything below is verified against the shipped product as of August 2026. If
something is not in this document, do not claim it.

---

## 1. In one paragraph

V-Rēķini is an online invoicing platform for Latvian businesses. You add a
client, add what you sold, and it produces a compliant PDF invoice — VAT
calculated, numbering handled, your logo on it — which you can email to the
client without leaving the app. It also does quotes, recurring invoices, client
and product records, stock, a revenue dashboard, structured PEPPOL e-invoices,
and exports for your accountant. It works in any browser including a phone.
Free to start, €2.99–€12.99 a month after that.

Company: **SIA "VN Media"**, reg. nr. 40203511357. Site: **v-rekini.lv**.

---

## 2. Who it is for

The core customer is a **micro business in Latvia that currently invoices in
Word or Excel**. Not people switching from another invoicing product — people
switching from a template file and manual numbering.

Concretely:

| Segment | What they look like | What pulls them in |
|---|---|---|
| Tradespeople & field services | Electricians, builders, installers, cleaners. 5–30 invoices a month | Invoice from the phone, right after the job |
| Consultants & freelancers | Designers, IT, marketing, bookkeeping-adjacent | Quotes that turn into invoices; recurring retainers |
| Small SIA with a few staff | 2–10 people, one person does the paperwork | Several people issuing under one company, one numbering |
| Anyone invoicing the public sector | Suppliers to state or municipal bodies | Structured e-invoices are **already required** |
| Anyone with an external accountant | Sends a folder of PDFs monthly | Excel export with the columns their accountant wants |

**Legal forms:** SIA, individuālais komersants (IK), saimnieciskās darbības
veicējs, pašnodarbinātie.

**Who it is NOT for:** companies needing a full accounting system (general
ledger, payroll, tax filing), anyone invoicing in a currency other than EUR,
anyone needing an API or integrations.

---

## 3. What it does

### Invoicing
- Sales and purchase documents, PDF output
- **Three invoice designs:** Klasiskā, Modernā, Minimālā
- Own logo and accent colour — the invoice looks like the customer's company
- VAT (PVN) calculated automatically; reverse charge supported; handles both
  VAT-registered and non-registered senders and recipients
- **Numbering:** three schemes, custom prefixes, and a "start from number N"
  setting so a business migrating from another system keeps its sequence
  unbroken
- Payment due dates, notes, per-line "included in price" flags
- Document statuses: issued / paid / overdue — with overdue surfaced on the
  dashboard

### Quotes (Piedāvājumi)
- Send a priced quote before the work
- Mark it **accepted / rejected** so the list can be triaged
- **One click turns a quote into an invoice** — client, line items, VAT and
  notes carry across; the quote is never modified and the two stay linked

### Clients & products
- Client records with full company details, VAT number, bank details
- **Latvian Business Register lookup** — start typing a company name and the
  registration number and legal address fill themselves in (from the official
  open data at dati.ur.gov.lv)
- One-off clients that do not clutter the main list
- Product/service catalogue with units

### Sending
- Email the invoice straight from the app
- Attach it as a **PDF or as a PEPPOL XML e-invoice** — the sender chooses
- Sent-email log

### E-invoices (this matters in Latvia right now)
- Generates structured e-invoices to **PEPPOL BIS Billing 3.0 / UBL 2.1**,
  conforming to LVS EN 16931-1:2017
- **Since 1 January 2025** structured e-invoices are already mandatory for
  invoicing state and municipal bodies (B2G)
- **From 1 January 2028** they become mandatory between businesses (B2B)
- Available on every paid plan

### Recurring invoices (Periodiskie rēķini)
- Set the frequency once; the invoice is created and emailed on schedule
- Monthly or a custom interval

### Stock (Preču atlikumi)
- For businesses selling goods rather than only services
- Purchase documents increase stock, sales documents decrease it

### For the accountant
- **Excel export** of a period — one sheet of documents, one of line items
- **The columns are user-defined.** Start from a template (Pilns / Pamata / PVN
  atskaitei), then rename, reorder, add and remove columns until they match
  exactly what the accountant or their software wants, and save that as your
  own layout
- **Bulk export:** every document in a period as one ZIP — PDFs or PEPPOL XML

### Dashboard
- Revenue, document count, average invoice, outstanding total
- Comparison against the previous period, with the in-progress month compared
  like-for-like (elapsed days vs elapsed days, not against a full past month)
- Revenue chart with day / week / month grouping
- Recent documents, overdue payments

### Team (Bizness plan)
- Several people working on the same invoices, clients and products
- One shared numbering sequence — no collisions
- Each person has their own login; the owner alone controls company settings,
  billing and who has access

### Housekeeping
- Trash with restore — a deleted document is recoverable
- Dark and light theme
- Works in any browser; installable to a phone home screen
- Data stored in Latvia, automatic daily backups

---

## 4. Plans

Prices in EUR. Yearly is roughly 18% cheaper (about two months free).

| | Bezmaksas | Mini | **Pamata** | Bizness | Mūža licence |
|---|---|---|---|---|---|
| Monthly | €0 | €2.99 | **€5.99** | €12.99 | €499 once |
| Yearly | — | €29 | **€59** | €129 | — |
| Documents / month | 5 | 50 | **500** | 5 000 | unlimited |
| Clients | 5 | 25 | **100** | 500 | unlimited |
| Products | 5 | 25 | **200** | 1 000 | unlimited |
| Emails / month | 3 | 30 | **100** | unlimited | unlimited |
| Invoice designs | basic | basic | **all 3** | all 3 | all 3 |
| Recurring invoices | — | — | **3** | unlimited | unlimited |
| E-invoices (PEPPOL) | — | ✓ | **✓** | ✓ | ✓ |
| Accountant export | — | — | **✓** | ✓ | ✓ |
| Stock | — | — | — | ✓ | ✓ |
| Users | 1 | 1 | **1** | 5 | unlimited |

- **Pamata is the one to push** — it is marked "Populārākais" and is where most
  customers should land.
- **Bizness** exists for two reasons: stock tracking and multiple users.
- **Mūža licence: only 10 will ever be sold.** This is a real, enforced cap —
  the counter is live. Do not write copy that survives them selling out.
- Free needs no credit card.

Payment is by card, Apple Pay or Google Pay, processed by **EveryPay** in
partnership with **SEB**. 3D Secure, PCI DSS. Card details never touch V-Rēķini.

---

## 5. Why someone picks it

Ranked by how much they actually move a decision:

1. **It replaces a Word file.** The competitor is not other software, it is a
   template document and hand-typed numbering. Numbering, VAT and layout stop
   being the customer's problem.
2. **It is built for Latvia.** Latvian language, Latvian VAT rules, Business
   Register lookup, Latvian numbering conventions, data held in Latvia. Not a
   foreign product with a translation layer.
3. **It is cheap.** Local competitors typically sit at €10–25/month. Pamata is
   €5.99 and there is a genuinely usable free tier.
4. **It works on a phone.** Invoice from the van, the site, the client's
   kitchen — not "when I get back to the computer".
5. **E-invoices are handled.** Already required for public-sector invoicing;
   required between businesses from 2028. No migration needed later.
6. **The accountant stops chasing files.** A whole month in one Excel or one
   ZIP, with the columns they asked for.

---

## 6. Do not claim

Copy must not say any of this, because it is not true:

- ❌ Compatible with Horizon / Jumis / Zalktis, or any named accounting
  package. The Excel export is **configurable to match whatever they need** —
  that is the claim, and it is a stronger one. No named compatibility has been
  tested.
- ❌ It is an accounting/bookkeeping system. It is not. No general ledger, no
  payroll, no VAT return filing.
- ❌ Multi-currency. EUR only.
- ❌ Bank-link payments at checkout. Cards and wallets only.
- ❌ API, Zapier, integrations with other software.
- ❌ Anything about migrating your data in from another system automatically.
  (You can continue your **numbering** — that is different, and true.)

---

## 7. Tone of voice

- **Latvian only.** Formal **Jūs**, never *tu* — the whole site uses Jūs and
  mixing them reads like two different companies.
- Calm, plain, concrete. Say what the thing does.
- **No hype, no exclamation marks, no "revolutionary".** The audience is
  practical people who dislike being sold to.
- Short sentences. Concrete nouns. "Rēķins gatavs 20 sekundēs" beats "efektīva
  rēķinu pārvaldības sistēma".
- Lead with the customer's irritation, not the feature name.

Examples of the register that works:

> Vai rēķinus joprojām rakstāt Word failā?
> Numerāciju un noformējumu sistēma sakārto pati.
> Grāmatvedim vairs nav jāsūta faili pa vienam.
> Darbs pabeigts. Rēķins izsūtīts. Vēl pirms izbraucat no pagalma.

---

## 8. Visual identity — for image generation

The look is **restrained and premium**. It was deliberately built *away* from
the colourful "AI dashboard" default. If a generated image looks like a
generic SaaS hero with purple gradients and floating 3D shapes, it is wrong.

### Colours

| Role | Dark (default) | Light |
|---|---|---|
| Page background | `#09090b` | `#fafaf9` |
| Card / panel | `#18181b` | `#ffffff` |
| Text | off-white | `#09090b` |
| Muted text | `#a1a1aa` | `#71717a` |
| Hairline borders | `#27272a` | `#e4e4e7` |
| Brand accent | `#3B82F6` (blue) — buttons and the logo mark only | same |

Near-monochrome. Blue appears **only** on primary buttons, the logo square and
the active nav item. Status colours (muted green / red / amber) appear only on
status pills. Nothing else is coloured.

### Type
DM Sans and Inter. Tight letter-spacing on headings (−0.5 to −0.8px). No
uppercase anywhere. Badges are lowercase with a 4–5px radius and a border, not
filled pills.

### UI shapes
- Cards: **no drop shadows**, 1px hairline border, 10px radius
- Sidebar: 240px, near-black, 13px medium nav labels with outline icons
- Tables: lowercase headers, hairline row separators
- Feature icons: thin outline strokes inside soft tinted rounded squares
  (violet, blue, emerald, amber, pink, cyan, rose) — the tint is subtle, the
  icon is the accent colour of that tint

### Logo
A blue rounded square with **VR** in white, followed by the wordmark
**V-Rēķini** in white/near-black semibold.

### Image directions that fit

Good subjects, roughly in order of usefulness:

1. **A phone held in a work environment** showing the invoice form or the
   dashboard — van interior, workshop bench, building site, café table.
   Natural light, real hands, slightly worn surroundings. Not a studio.
2. **A laptop on a real desk** with the dark dashboard on screen — plant,
   coffee, notebook, Latvian daylight. Calm, not staged.
3. **A clean invoice PDF** on screen or freshly printed on a desk, with the
   company logo visible.
4. **Portrait of the customer**: 30–55, Latvian/Baltic, working clothes or
   smart-casual, in their own workplace. Documentary photography, not stock
   smiling.
5. **Split before/after**: a chaotic Word document and folder of files versus
   the clean app. Restrained, no red crosses and green ticks.

### Image directions to avoid
- Purple/pink gradients, glassmorphism, neon
- Floating 3D shapes, abstract blobs, isometric illustration
- Overly diverse smiling stock-photo office teams
- Anything that looks American or Silicon Valley
- Money imagery: coins, stacks of cash, piggy banks, dollar signs
- Robots, AI brains, circuit boards

### Prompt fragments that steer it right
> "documentary photography, natural window light, Northern European,
> understated, muted colour palette, real workplace, shot on 35mm, shallow
> depth of field, no text overlays"

For UI mockups:
> "dark UI, near-black `#09090b` background, `#18181b` cards, hairline borders,
> no drop shadows, single blue `#3B82F6` accent on the primary button only,
> DM Sans typography, generous whitespace, minimal, premium, restrained"

---

## 9. Fact sheet — numbers safe to quote

- Free plan: **5 documents a month, 5 clients, 5 products, 3 emails** — no card
- Pamata: **€5.99/month or €59/year**
- Bizness: **€12.99/month or €129/year** — includes stock and **5 users**
- Lifetime: **€499 once, 10 licences only**
- Yearly billing saves about **18%**
- **3** invoice designs
- **3** numbering schemes
- E-invoice standard: **PEPPOL BIS Billing 3.0 / UBL 2.1, LVS EN 16931-1:2017**
- B2G e-invoices mandatory since **1 January 2025**
- B2B e-invoices mandatory from **1 January 2028**
- Accountant export produces **2 sheets**: Dokumenti and Pozīcijas
- Data stored in **Latvia**, backed up **daily**
- Payments: **EveryPay + SEB**, 3D Secure, PCI DSS
- Company: **SIA "VN Media"**, reg. nr. **40203511357**
