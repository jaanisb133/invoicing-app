# V-Rēķini screenshots for vnmedia.lv

Real screens of the app on a fictional account (SIA "Ziemeļu Kadrs", a photo studio, and its
clients; `*.example` e-mails, `LV00UNLA…` IBAN), so they are safe to publish. Desktop at
1440×900 and phones at 390×844, both at 2× (WebP).

| File | What |
|---|---|
| `v-rekini-dashboard-dark.webp` / `-light` | Pārskats: this year by month, KPI strip, Termiņi, overdue finding |
| `v-rekini-editor-dark.webp` / `-light` | New invoice: client, two lines, live paper preview |
| `v-rekini-invoice-dark.webp` | An issued invoice: paper view, template switch, lock note |
| `v-rekini-documents-dark.webp` | The invoice list with paid / awaiting / overdue |
| `v-rekini-phone-*-dark.webp` | Phone: dashboard, editor lines, invoice, list |
| `v-rekini-phones-dark.webp` | Three phones side by side, transparent ground |
| `v-rekini-templates.webp` | The three PDF designs of one invoice, transparent ground |
| `v-rekini-landing.webp` | The public landing page, first screen |

Regenerate after UI changes (dates are relative to the day you run it):

    VREKINI_DB_PATH=/tmp/showcase.db python scripts/footage/showcase.py
    VREKINI_DB_PATH=/tmp/showcase.db uvicorn app.main:app --port 8766 &
    VREKINI_DB_PATH=/tmp/showcase.db python scripts/footage/screens.py --out /tmp/shots [--chromium …] [--vendor …]

then convert the PNGs to WebP (quality 92) under these names; the phones and templates
composites are three images in a row with 72 / 64 px gaps.
