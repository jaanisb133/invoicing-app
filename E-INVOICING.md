# E-rēķini and VID — what the law and VID require, and what V-Rēķini must do

Researched 2026-10-21 from primary sources (list at the end). VID's own material is
dated up to 05.10.2026. Anything marked **UNKNOWN** could not be confirmed from a
public source; the section "Open questions" says how to settle each one.

## 1. Bottom line

- **Who must:** every Latvian business (companies, IK, self-employed, associations) issuing
  an invoice to another Latvian business. B2G already: e-invoice since 01.01.2025,
  VID submission since 01.01.2026. B2B: both from **01.01.2028**; voluntary until then.
  Private persons (B2C) and foreign clients: not required (foreign planned ~2030).
- **What counts:** only the XML (UBL 2.1, PEPPOL BIS Billing 3.0, LVS EN 16931-1).
  A PDF is not an e-invoice, so a PDF-only invoice is not a valid justification document
  for payment where an e-invoice is required.
- **VID submission:** once, within **5 working days** after the day it was sent to the
  client (MK 749 p.14), counted from the next working day. VID example: sent Mon
  01.06.2026, deadline Mon 08.06.2026.
- **An e-invoice can never be deleted.** Mistakes and cancellations are fixed only by
  issuing a new e-invoice that references the old number (MK 877 p.25.1). That new
  document must be submitted to VID too.
- **The duty sits with the issuer**, or with the operator they chose. If V-Rēķini
  submits for a user and fails, the user is still the one in breach, so the app must
  show status and deadlines and never fail silently.

## 2. The ways an e-invoice reaches VID (MK 749 p.4, 10–13)

| Delivery to client (p.4) | How VID gets it (p.10) | What it means for V-Rēķini |
|---|---|---|
| **E-adrese** (latvija.gov.lv, or an integration via VDAA) | Automatic copy (p.11) | Sending through e-adrese also files with VID. Every UR-registered company has had a mandatory e-adrese since 01.01.2023, so this reaches almost all B2B clients. Integration requires VDAA onboarding (see §6). |
| **Operator** (a service provider that delivers it, e.g. via PEPPOL) | Operator's channel integrated with VID API (p.12) | V-Rēķini would have to *be* a delivery operator: PEPPOL access point (AS4) or e-adrese participant. VID lists recommended (not binding) requirements: EN 16931 + PEPPOL BIS 3.0, VID ISS API, AS4, TLS 1.2/1.3, audit log, SLA, DPA with clients. |
| **Other channel: e-mail, system integration** (what V-Rēķini does today) | **The issuer** files via EDS API or EDS upload (p.13) | Today's e-mail sending falls here. VID's own example 7 is exactly us: "a website that offers e-invoice creation, sent to the partner by e-mail". So filing must go through **EDS API with the user's own credential**, or a manual upload. |

Also: partners agree between themselves which channel to use (p.5). Filing once
through one channel is enough; never file the same invoice again through another (p.14).

## 3. EDS API: the credential reality

- Service: **"E-Rēķini (E-Invoice API V2)"**. It is one of four EDS API services, max 20 MB
  per invoice, OpenAPI 3.0. Its swagger is only shown inside EDS (Iestatījumi → API
  atslēgu pārvaldība), so the endpoint and payload are **UNKNOWN** until someone with an
  EDS login exports it.
- Auth: an **API key or API certificate** created in EDS (Iestatījumi → API atslēgas,
  scope "Dokumentu API (izmanto arī e-rēķiniem)"). Username and password have not been
  accepted since 01.01.2026.
- **Validity is at most 90 days**, for keys and certificates alike. Moneo asked VID for
  longer-lived keys and was told no. A key can't be viewed again after creation.
- The credential is bound to **one person + one taxpayer**. The person must be the
  company's signing official or hold a VID-registered power of attorney (pilnvara).
  Optional IP allow-list. Rate limits per minute.
- So for each V-Rēķini account: the owner logs into EDS (Smart-ID/eParaksts), creates a
  certificate, uploads it to us, and **repeats every ≤ 90 days**. We must store it
  encrypted, warn before expiry, and queue invoices (with the deadline visible) while
  it's missing.

## 4. VID-side behaviour

- **Validation:** antivirus + XSD + PEPPOL Schematron. On failure the invoice goes to
  "Izsniegtie noraidītie" in EDS with a detailed error, and VID sends an informational
  notice. A rejected invoice counts as not filed.
- **Duplicates:** VID treats only a byte-identical XML as a duplicate. The same number
  with any change (even whitespace) is stored as a second invoice. So **freeze the
  exact XML bytes at filing time**; retries resend those bytes, and never a
  regenerated file.
- **Recipient can mark it "neatbilstošs"** (e.g. wrong recipient) once, with a reason.
  It moves to "Neatbilstošie" for both sides. The issuer then cancels it with a credit
  note. Whether the API exposes this flag is **UNKNOWN**.
- **Payment status** in EDS (neapmaksāts / daļēji / apmaksāts) is optional, and VID
  doesn't use it.
- **VAT return:** EDS can prefill PVN 1-I / 1-III from filed e-invoices **by issue
  date** (it warns about invoices of ≥ 150 € missing from the return). Advance invoices
  belong in the return only when paid.
- VID stores invoices **without attachments**.

## 5. Lifecycle cases: what happens and what the app must do

| Case | Rule (source) | App behaviour |
|---|---|---|
| Error found **before sending** | Not issued yet | Free to edit (draft). |
| Sent to client, **not yet filed**, error found | Still issued; must be filed once within 5 wd (MK 749 p.14). Corrected by a new document referencing it (MK 877 p.25.1) | Lock on send. File the original; issue a correction. Never overwrite and refile. |
| **Wrong price/amount/details** | Either a **corrective invoice**: new number, "Iepriekšējā rēķina numurs" (BT-25). VID treats it as replacing the original and puts it in the **original's period**. Or a **full credit note + new invoice** (what latvija.gov.lv does). The choice belongs to the company's accounting policy; VID sets no strict method | Offer both. Default to credit note + new invoice: clearest for small users and the official-portal pattern. |
| **Deal cancelled entirely** ("terminated later") | Credit note (type 381) for the full amount, referencing the original number and date. Amounts **positive**: the type does the crediting (VID guidelines p.22–23) | "Anulēt" action → creates a credit note, files it, and marks the original as cancelled. The original stays visible forever. |
| **Partial** cancel, discount, return, refunded advance | Credit note for the **difference only**, counted in the credit note's own period (VID 04.12.2025 slides) | Credit note with selected lines/amounts. |
| Client says **wrong recipient** | Client marks it "neatbilstošs" in EDS; issuer issues a credit note (VID example 21) | Same as cancellation. |
| **VID rejects** (XSD/Schematron) | If already in the books: credit note + new e-invoice. If not booked: issue a new correct one (VID guidelines p.27) | Validate before filing so this is rare. On rejection: show the error and offer "fix and reissue". |
| **Advance invoice** (386) | Issue it as an e-invoice only if it's a real payment request. If fully paid, no final invoice is needed, provided another document links delivery to the payment (MK 877 p.34.1–34.2). A final invoice must reference the advance number. Cancelled advance → credit note | Support type 386 and a reference on the final invoice. |
| **Our outage** past the deadline | Notify VID in EDS "Sarakste ar VID" by the next working day after the deadline, with the reason; file within 3 wd after the fix (MK 749 p.15) | Detect it, then tell the user exactly what to write and by when. There's no API for "Sarakste" (**UNKNOWN**). |
| **VID outage** | File by the next working day after VID announces the fix (p.16) | Retry queue that honours VID's announcement. |
| **Missed for other reasons** (forgot, new accountant) | Notify VID with reason and period; file within 30 days of discovery (p.17) | "Nav iesniegts" list with a guided catch-up. |
| **Private person** client | No e-invoice duty; PDF fine | Don't file; the PDF stays primary. |
| **Foreign** client | Not required (agreed use allowed) | Don't file by default. |
| **Budget institution** client (pašvaldība, school…) | Mandatory **now**: e-invoice since 2025, VID filing since 2026. Check via the CSP ISK lookup | Mark such clients, warn when a PDF-only invoice goes to them, and file. |
| **Deleting** an invoice | Not possible for e-invoices; accounting documents must be kept (GL 28) | **Block delete** once sent or filed. Numbers are never reused. |

## 6. E-adrese route (the "send and forget" option)

- Sending an EINVOICE-type message through e-adrese delivers to the client's e-adrese
  **and** files a copy with VID automatically. This needs the current VDAA integration
  library (older versions must address `VID_EREKINI@90000069281` by hand).
- E-adrese is transport only and doesn't validate. VID still validates the copy.
- **Operator onboarding** (VDAA "Kā kļūt par e-adreses sistēmas dalībnieku"):
  1. The operator has an active e-adrese.
  2. VDAA creates "accepts e-invoices only" connections for the operator.
  3. Each client has an active e-adrese and creates a sub-addressee (e.g.
     `EINVOICE@<reg.nr.>`).
  4. A **form signed by both client and operator** goes to VDAA to attach that
     sub-addressee to the operator's connection.
  5. For EU recipients, the operator must also be a PEPPOL access point with a VDAA
     contract.
  
  So it's a one-time setup per client with a signed form. That's friction, but no
  90-day renewal.
- Latvija.gov.lv now lets a company authorise someone (e.g. an accountant) to access
  only e-invoices. How that maps to third-party software is **UNKNOWN**.
- Scale: 1 146 593 e-invoice messages through e-adrese by 13.11.2025.

## 7. What's wrong in V-Rēķini today (`app/einvoice.py` and around it)

These would fail VID's Schematron or the rules above:

1. **Non-VAT-payer invoices** are written as category `Z` with `Percent 0`. PEPPOL
   requires a seller VAT ID for `Z`, so every non-VAT-payer XML is rejected. The
   correct category is `O` ("Darījumi, kas neietilpst PVN darbības jomā", as VID's FAQ
   says), with no Percent and an exemption reason.
2. **Rounding:** the header totals come from the unrounded sum, while each line is
   rounded on its own. Example: two lines of 1,5 × 0,33 give lines 0,49 + 0,49 but a
   total of 0,99, which breaks BR-CO-10 (checked: Python rounds 0,495 to 0,49).
   Quantities and prices are also cut to 2 decimals, so a line like 1000 × 0,0145
   prints as 1000 × 0,01 = 14,50 and fails the line check. The fix is line-rounded totals everywhere:
   PDF, preview and XML must agree, and the XML is the legal document. (This settles
   the "per-line rounding" item in CLAUDE.md.)
3. **EndpointID** always uses scheme `9939` (Latvian VAT number), even when the value
   is a registration number. Use `0218` (Latvian unified registration number) for a
   reg. no. For persons it falls back to `"N/A"`.
4. **The VAT number's `LV` prefix isn't enforced**. PEPPOL requires the country prefix.
5. **The buyer country is hardcoded `LV`**, which is wrong for foreign clients.
6. **No credit note (381), corrective reference (BT-25) or advance (386)**. Only 380
   exists.
7. **Invoices stay editable after sending.**
8. **Delete → trash → hard purge after 7 days, and the number is reused on restore.**
   For e-invoices this is impossible, and it already conflicts with GL 28 retention.
9. **No validation before export** (the EC validator at itb.ec.europa.eu/invoice is
   what VID recommends).

## 8. Suggested build order

1. **Correct XML** (§7 items 1–5, 9) plus line-rounded totals. Without this, nothing
   else matters. Self-check against the EC validator on sample invoices.
2. **Issued-document integrity:** lock on send, "Anulēt" via credit note, corrective
   invoice, no delete or number reuse for sent invoices.
3. **Filing tracker:** per-invoice status (nav jāiesniedz / jāiesniedz līdz dd.mm. /
   iesniegts / noraidīts) with a Latvian working-day calendar. Manual filing at first:
   download XML → EDS upload, or latvija.gov.lv upload, which also delivers via e-adrese.
4. **EDS API filing** with the user's certificate (90-day renewal reminders, encrypted
   storage, frozen XML, retry queue).
5. **E-adrese operator integration** (VDAA) for real one-click B2B delivery + filing.

## 9. Open questions and how to settle them

- **E-Invoice API V2 spec** (endpoints, payload, responses, statuses, test environment):
  log into EDS → Iestatījumi → API atslēgu pārvaldība → download the swagger.json. It's
  not secret. Ask VID in EDS "Sarakste ar VID" (tēma "E-rēķini") for test environment
  access.
- **Operator route via the VID API** (one credential for all clients, MK 749 p.10.2):
  ask VID through the same channel, and ask to be added to the provider list (subject
  "Iekļaušana e-rēķinu pakalpojumu sniedzēju sarakstā"). Numbero, Moneo and others are
  on it.
- **VDAA integration docs:** viss.gov.lv → Dokumentācija → Vadlīnijas → e-adrese; support
  atbalsts@vdaa.gov.lv. These sites, plus vdaa.gov.lv, latvija.gov.lv, eds.vid.gov.lv and
  docs.peppol.eu, were blocked from this cloud session.
- **LVS EN 16931-1** is free (EC-funded) at lvs.lv after registering.

## Sources

- MK 09.12.2025 noteikumi Nr. 749 (likumi.lv/ta/id/365040), in force 13.12.2025.
- MK 21.12.2021 noteikumi Nr. 877, p.25.1, 31.1, 34.1–34.2 (grozījumi 23.09.2025), via
  VID informatīvais materiāls 25.09.2025 (vid.gov.lv/lv/media/31802).
- Grāmatvedības likums 1., 3., 11. pants, pārejas noteikumi 8.–10.; Oficiālās
  elektroniskās adreses likums, pārejas noteikumi 3. punkts.
- VID "E-rēķinu noformēšanas vadlīnijas", 30.09.2026 (vid.gov.lv/lv/media/35808).
- VID e-rēķini page (vid.gov.lv/lv/e-rekini, upd. 05.10.2026) and FAQ
  (vid.gov.lv/lv/biezak-uzdotie-jautajumi-katalogs/e-rekini, upd. 15.05.2026).
- VID "EDS API servisa apraksts" (upd. 02.03.2026) and "EDS API izstrādātāju rokasgrāmata".
- VID "E-rēķinu nosūtīšanas varianti ar kopijas nodošanu VID" (media/33806), "Soli pa solim:
  e-rēķinu iesniegšana un apstrāde VID EDS" (media/33803), "Strukturētie e-rēķini – aprite
  un iesniegšana VID" 04.12.2025 (media/32816), MK 749 informatīvais materiāls (media/32903),
  "Informācija e-rēķinu pakalpojuma sniedzējam" (media/28314), "E-rēķinu pakalpojuma
  sniedzēju saraksts" 28.09.2026 (media/27231), VDAA "E-rēķinu aprite e-adresē"
  04.12.2025 (media/32828).
- Moneo blog "Izmaiņas VID EDS autentifikācijā" (90-day keys, VID's answer), via search
  excerpt; Zalktis help (certificate bound to user + company), via search excerpt.
