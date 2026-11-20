"""
Client list import from CSV or Excel (Klienti → Importēt).

Reads the file into a header and rows, guesses which column is which from its
header (Latvian and English names, the way Zalktis, Numbero, Excel lists and
bank exports write them), and turns each row into a client the way the add-client
form would. The person checks the guess on a preview page and can change any
column before anything is saved.
"""

import csv
import datetime
import io
import re
import unicodedata

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000

# What a column can be, in the order the preview offers them
FIELDS = [
    ("name", "Nosaukums vai vārds"),
    ("reg_number", "Reģ. nr. vai personas kods"),
    ("vat_number", "PVN nr."),
    ("legal_address", "Adrese"),
    ("email", "E-pasts"),
    ("phone", "Tālrunis"),
    ("contact_person", "Kontaktpersona"),
    ("bank_name", "Banka"),
    ("bank_account", "Konts (IBAN)"),
]
FIELD_LABELS = dict(FIELDS)

# Header words, plain (no diacritics, lower case). Checked in this order, so
# "PVN reģ. nr." is a VAT number before it can be a registration number,
# "bankas konts" an account before it can be a bank and "e-pasta adrese" an
# e-mail before it can be an address. A bare "Kods" is left out: in accounting
# exports it is usually the program's own client code, not the reg. no.
ADDRESS_PART = "address_part"      # city, postal code: joined onto the address

_HEADER_RULES = [
    ("vat_number", ("pvn", "vat", "nodokla maksataja", "nodoklu maksataja")),
    ("email", ("e pasts", "e pasta", "epasts", "email", "e mail", "mail")),
    ("bank_account", ("iban", "konts", "konta nr", "norekinu", "account")),
    ("bank_name", ("banka", "bankas nosaukums", "bank")),
    ("reg_number", ("reg", "registracijas", "personas kods", "pers kods", "p k", "registration")),
    ("phone", ("talrunis", "telefons", "talr", "tel", "mob", "phone")),
    ("contact_person", ("kontaktpersona", "kontakts", "kontaktpers", "contact")),
    (ADDRESS_PART, ("pilseta", "city", "pasta indekss", "pasta kods", "indekss",
                   "zip", "postal", "novads")),
    ("legal_address", ("adrese", "juridiska", "address", "adr")),
    ("name", ("nosaukums", "klients", "klienta", "uznemums", "partneris", "pircejs",
              "sanemejs", "vards", "name", "company", "client", "customer", "firma")),
]


def _plain(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _guess(header):
    h = _plain(header)
    if not h:
        return ""
    words = h.split()
    for field, keys in _HEADER_RULES:
        for key in keys:
            if key == h or (" " in key and key in h) or key in words or any(w.startswith(key) for w in words if len(key) >= 4):
                return field
    return ""


def guess_field(header):
    """The field a column header most likely means, or "" to leave it out."""
    field = _guess(header)
    return "legal_address" if field == ADDRESS_PART else field


def guess_mapping(header):
    """One field per column. A field goes to its first matching column only, except
    the reg. no. (a list may have "Reģ. nr." and "Personas kods" side by side) and the
    parts of an address (street, city, postal code), which are joined."""
    taken, mapping = set(), []
    for col in header:
        field = _guess(col)
        if field == ADDRESS_PART:
            mapping.append("legal_address")
        elif field and (field not in taken or field == "reg_number"):
            taken.add(field)
            mapping.append(field)
        else:
            mapping.append("")
    return mapping


# --- reading ----------------------------------------------------------------

class ImportError_(ValueError):
    """A file we can't read, with the reason in Latvian."""


def _cell(value):
    """A cell as text: Excel numbers keep their digits (40003012345, not 4.0003e10),
    dates read as dd.mm.yyyy."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else ""
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.strftime("%d.%m.%Y")
    return str(value).strip()


def _trim(rows):
    """Drop empty rows and the empty columns at the right; the first row left is the header."""
    rows = [[_cell(v) for v in r] for r in rows]
    rows = [r for r in rows if any(v for v in r)]
    if not rows:
        raise ImportError_("Failā nav datu.")
    # A report may open with a title ("Klientu saraksts 2026"): the header is the first
    # of the top rows that names at least two fields we know
    start = next((i for i, r in enumerate(rows[:10]) if sum(1 for v in r if guess_field(v)) >= 2), 0)
    rows = rows[start:]
    width = max(max((i + 1 for i, v in enumerate(r) if v), default=0) for r in rows)
    rows = [(r + [""] * width)[:width] for r in rows]
    header, data = rows[0], rows[1:]
    if not data:
        raise ImportError_("Failā ir tikai virsrakstu rinda, bet nav neviena klienta.")
    if len(data) > MAX_ROWS:
        raise ImportError_(f"Failā ir {len(data)} rindu; vienā reizē var ielādēt līdz {MAX_ROWS}.")
    return [h or f"{i + 1}. kolonna" for i, h in enumerate(header)], data


def read_file(filename, content):
    """(header, rows) from an uploaded CSV or XLSX. Raises ImportError_."""
    name = (filename or "").lower()
    if len(content) > MAX_BYTES:
        raise ImportError_("Fails ir lielāks par 5 MB.")
    if not content:
        raise ImportError_("Fails ir tukšs.")
    if name.endswith((".xls", ".ods")) and not content.startswith(b"PK"):
        raise ImportError_("Šo formātu nevaram nolasīt. Saglabājiet failu kā .xlsx vai CSV un ielādējiet vēlreiz.")
    if content.startswith(b"PK"):          # .xlsx is a zip
        return _read_xlsx(content)
    return _read_csv(content)


def _read_xlsx(content):
    try:
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception:
        raise ImportError_("Šo Excel failu neizdevās atvērt. Saglabājiet to kā .xlsx vai CSV un mēģiniet vēlreiz.")
    try:
        ws = wb.worksheets[0]
        rows = []
        for i, r in enumerate(ws.iter_rows(values_only=True)):
            if i > MAX_ROWS + 50:
                break
            rows.append(list(r))
    finally:
        wb.close()
    return _trim(rows)


def _read_csv(content):
    # Excel in Latvia saves CSV as UTF-8 (with a BOM) or as Windows-1257
    for enc in ("utf-8-sig", "cp1257"):
        try:
            text = content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ImportError_("Faila kodējumu neizdevās nolasīt. Saglabājiet to kā CSV UTF-8.")
    first, _, rest = text.partition("\n")
    if first.strip().lower().startswith("sep=") and len(first.strip()) == 5:
        return _trim(list(csv.reader(io.StringIO(rest), delimiter=first.strip()[4])))
    sample = text[:20000]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=";,\t").delimiter
    except csv.Error:
        delimiter = ";" if sample.count(";") >= sample.count(",") else ","
    return _trim(list(csv.reader(io.StringIO(text), delimiter=delimiter)))


# --- one row -> one client ---------------------------------------------------

_COMPANY = re.compile(r"\b(sia|as|ik|zs|ps|ks|biedrība|biedriba|nodibinājums|nodibinajums|"
                      r"pašvaldība|pasvaldiba|ltd|llc|gmbh|oy|ab|uab|ou|oü)\b", re.I)
_EMAIL = re.compile(r"[^@\s;,]+@[^@\s;,]+\.[^@\s;,]+")


def _is_person_code(reg):
    """A Latvian personas kods: 6+5 digits, written with a hyphen, or the new 32… form,
    or the old one that starts with a day (0–3); a company's reg. no. starts with 4, 5 or 9."""
    digits = re.sub(r"\D", "", reg)
    if len(digits) != 11:
        return False
    return "-" in reg or digits.startswith("32") or digits[0] in "0123"


def to_client(values, mapping):
    """(client dict, problem) for one row: problem is a Latvian reason the row is
    skipped ("" when it is fine)."""
    row, address = {}, []
    for field, value in zip(mapping, values):
        value = value.strip()
        if not field or not value:
            continue
        if field == "legal_address":
            if re.fullmatch(r"\d{4}", value):              # a postal code from a number cell
                value = "LV-" + value
            if not any(_plain(value) in _plain(part) for part in address):
                address.append(value)
        elif not row.get(field):
            row[field] = value
    row["legal_address"] = ", ".join(address)
    name = re.sub(r"\s+", " ", row.get("name", "")).strip()[:200]
    if not name:
        return None, "nav nosaukuma"
    reg = re.sub(r"\s+", "", row.get("reg_number", ""))[:30]
    vat = re.sub(r"[\s.]+", "", row.get("vat_number", "")).upper()[:30]
    if reg.upper().startswith("LV") and reg[2:].isdigit():     # a VAT number in the reg. no. column
        vat = vat or reg.upper()
        reg = reg[2:]
    if vat.isdigit() and len(vat) == 11:
        vat = "LV" + vat
    person = bool(reg) and _is_person_code(reg) and not _COMPANY.search(name)
    email = _EMAIL.search(row.get("email", ""))
    return {
        "name": name,
        "client_type": "individual" if person else "business",
        "reg_number": reg,
        "vat_number": "" if person else vat,
        "vat_payer": 1 if vat and not person else 0,
        "legal_address": re.sub(r"\s+", " ", row.get("legal_address", "")).strip()[:300],
        "email": email.group(0)[:200] if email else "",
        "phone": row.get("phone", "")[:50],
        "contact_person": row.get("contact_person", "")[:120],
        "bank_name": row.get("bank_name", "")[:120],
        "bank_account": re.sub(r"\s+", "", row.get("bank_account", "")).upper()[:40],
    }, ""


def plan(rows, mapping, existing, room):
    """What importing would do, row by row: [{"n", "client", "status", "note"}].

    existing: the account's clients (reg. no. and name decide a duplicate);
    room: how many more clients the plan allows (None = no limit).
    Status "new" rows are the ones to save."""
    seen_reg = {(c.get("reg_number") or "").strip() for c in existing if c.get("reg_number")}
    seen_name = {_plain(c.get("name")) for c in existing}
    out, added = [], 0
    for i, values in enumerate(rows, start=2):        # row 1 is the header
        client, problem = to_client(values, mapping)
        if problem:
            out.append({"n": i, "client": None, "status": "skip", "note": problem})
            continue
        key_name = _plain(client["name"])
        if client["reg_number"] and client["reg_number"] in seen_reg:
            out.append({"n": i, "client": client, "status": "dup", "note": "jau sarakstā (tas pats reģ. nr.)"})
            continue
        if not client["reg_number"] and key_name in seen_name:
            out.append({"n": i, "client": client, "status": "dup", "note": "jau sarakstā (tāds pats nosaukums)"})
            continue
        if room is not None and added >= room:
            out.append({"n": i, "client": client, "status": "limit", "note": "pārsniedz plāna klientu limitu"})
            continue
        if client["reg_number"]:
            seen_reg.add(client["reg_number"])
        seen_name.add(key_name)
        added += 1
        out.append({"n": i, "client": client, "status": "new", "note": ""})
    return out


# --- the sample the page offers -----------------------------------------------

SAMPLE_HEADER = ["Nosaukums", "Reģ. nr. / personas kods", "PVN nr.", "Juridiskā adrese",
                 "E-pasts", "Tālrunis", "Kontaktpersona", "Banka", "Konts (IBAN)"]
SAMPLE_ROWS = [
    ['SIA "Bērzu Darbnīca"', "40003000001", "LV40003000001", "Pils iela 3, Sigulda, LV-2150",
     "birojs@example.lv", "+371 20000001", "Anna Bērziņa", "Swedbank", "LV00HABA0000000000001"],
    ['SIA "Ziemeļu Kadrs"', "40003000002", "", "Rīgas iela 10, Valmiera, LV-4201",
     "info@example.lv", "", "", "", ""],
    ["Jānis Paraugs", "", "", "Liepu iela 5, Cēsis, LV-4101", "janis@example.lv", "", "", "", ""],
]


def sample_csv():
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(SAMPLE_HEADER)
    w.writerows(SAMPLE_ROWS)
    return ("﻿" + buf.getvalue()).encode("utf-8")       # BOM: Excel opens it as UTF-8


def sample_xlsx():
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook()
    ws = wb.active
    ws.title = "Klienti"
    ws.append(SAMPLE_HEADER)
    for r in SAMPLE_ROWS:
        ws.append(r)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for col, width in zip("ABCDEFGHI", (28, 24, 18, 36, 24, 16, 20, 14, 26)):
        ws.column_dimensions[col].width = width
    # Registration numbers are text, so Excel keeps them whole
    for row in ws.iter_rows(min_row=2, min_col=2, max_col=3):
        for cell in row:
            cell.number_format = "@"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
