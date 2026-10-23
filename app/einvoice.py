"""
E-invoice (e-rēķins) generator for V-Rēķini.

Writes UBL 2.1 XML to PEPPOL BIS Billing 3.0 (EN 16931, LVS EN 16931-1:2017):
an Invoice (380), a corrective invoice (384, pointing at the invoice it
replaces) or a CreditNote (381, pointing at the invoice it credits). VID
rejects anything that fails the PEPPOL Schematron, so the rules that bite are
handled here and `problems()` names what the user still has to fill in.
See E-INVOICING.md for the law behind it.

Amounts follow app/money.py: lines rounded to the cent, VAT on their sum.
Reference: https://docs.peppol.eu/poacc/billing/3.0/
"""

import re
import tempfile
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

from app import database as db
from app import money

NS_INVOICE = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
NS_CREDIT = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
ET.register_namespace("cac", NS_CAC)
ET.register_namespace("cbc", NS_CBC)

CUSTOMIZATION_ID = "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
PROFILE_ID = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"
CURRENCY = "EUR"

# Electronic address schemes (PEPPOL EAS) and legal identifier schemes (ICD)
SCHEME_LV_REG = "0218"   # Latvian unified registration number (Uzņēmumu reģistrs)
# VAT numbers as electronic addresses, by country prefix (PEPPOL EAS code list)
VAT_SCHEMES = {
    "LV": "9939", "LT": "9937", "EE": "9931", "PL": "9945", "DE": "9930",
    "AT": "9914", "BE": "9925", "BG": "9926", "CY": "9928", "CZ": "9929", "EL": "9933",
    "HR": "9934", "IE": "9935", "LU": "9938", "MT": "9943", "NL": "9944", "PT": "9946",
    "RO": "9947", "SI": "9949", "SK": "9950", "ES": "9920", "FR": "9957", "HU": "9910",
    "IT": "0211", "GB": "9932", "CH": "9927",
}

# App unit names → UN/ECE Recommendation 20
UNIT_CODE_MAP = {
    "gab": "C62", "gab.": "C62", "pakalp.": "C62", "pakalpojums": "C62",
    "h": "HUR", "st.": "HUR", "st": "HUR", "stunda": "HUR", "stundas": "HUR",
    "diena": "DAY", "dienas": "DAY", "d.": "DAY",
    "mēn.": "MON", "mēnesis": "MON", "gads": "ANN",
    "kompl.": "SET", "komplekts": "SET",
    "kg": "KGM", "t": "TNE", "l": "LTR",
    "m": "MTR", "m²": "MTK", "m2": "MTK", "m³": "MTQ", "m3": "MTQ", "km": "KMT",
    "kaste": "CT", "iepak.": "PK", "pak.": "PK", "lpp.": "C62", "kWh": "KWH",
}


def _unit_code(unit_text):
    if not unit_text:
        return "C62"
    return UNIT_CODE_MAP.get(unit_text.strip(), UNIT_CODE_MAP.get(unit_text.strip().lower(), "C62"))


def _lv_reg(value):
    """An 11-digit Latvian registration number, or ''."""
    digits = re.sub(r"\D", "", value or "")
    return digits if len(digits) == 11 else ""


def _vat_id(value):
    """A VAT number with its country prefix: '40003...' → 'LV40003...'."""
    v = re.sub(r"\s", "", value or "").upper()
    if re.fullmatch(r"\d{11}", v):
        return "LV" + v
    return v


def _country(party):
    vat = _vat_id(party.get("vat"))
    return vat[:2] if re.match(r"^[A-Z]{2}", vat) and vat[:2] != "EL" else (
        "GR" if vat.startswith("EL") else "LV")


def _dec_text(value):
    """A quantity or unit price exactly as entered: 1.5, 0.0145, 120."""
    d = money.dec(value).normalize()
    s = format(d, "f")
    return s if "." not in s else s.rstrip("0").rstrip(".") or "0"


def _amount(parent, tag, value):
    el = SubElement(parent, f"{{{NS_CBC}}}{tag}")
    el.set("currencyID", CURRENCY)
    el.text = f"{money.cents(value):.2f}"
    return el


def _text(parent, tag, value, ns=NS_CBC, **attrs):
    el = SubElement(parent, f"{{{ns}}}{tag}")
    for k, v in attrs.items():
        el.set(k, v)
    el.text = str(value)
    return el


def _get_einvoice_data(doc_id):
    doc, items = db.get_document(doc_id)
    if not doc:
        raise ValueError(f"Dokuments ar ID {doc_id} nav atrasts")
    client = db.get_client(doc["client_id"], doc["user_id"]) or {}
    user_id = doc.get("user_id", 0)
    settings = db.get_all_user_settings(user_id) if user_id else db.get_all_settings()
    user = (db.get_user(user_id) if user_id else None) or {}

    own = {
        "name": (settings.get("company_name") or "").strip(),
        "reg": (settings.get("reg_number") or "").strip(),
        "vat": (settings.get("vat_number") or "").strip(),
        "addr": (settings.get("legal_address") or "").strip(),
        "account": (settings.get("bank_account") or "").strip(),
        "email": (settings.get("company_email") or user.get("email") or "").strip(),
        "phone": (settings.get("company_phone") or "").strip(),
        "person": settings.get("entity_type") == "individual",
        "vat_payer": settings.get("is_vat_payer", "1") == "1",
    }
    other = {
        "name": (client.get("name") or "").strip(),
        "reg": (client.get("reg_number") or "").strip(),
        "vat": (client.get("vat_number") or "").strip(),
        "addr": (client.get("legal_address") or "").strip(),
        "account": (client.get("bank_account") or "").strip(),
        "email": (client.get("email") or "").strip(),
        "phone": (client.get("phone") or "").strip(),
        "person": (client.get("client_type") or "business") == "individual",
        "vat_payer": bool(client.get("vat_payer")) or bool(client.get("vat_number")),
    }
    supplier, buyer = (other, own) if doc["doc_type"] == "buy" else (own, other)

    reverse = bool(doc.get("reverse_charge"))
    rate = 0.0 if reverse else float(doc.get("vat_rate") or 0)
    if not supplier["vat_payer"]:
        category = "O"
    elif reverse:
        category = "AE"
    elif rate == 0:
        category = "Z"
    else:
        category = "S"
    if category == "O":
        rate = 0.0

    # The XML is checked line by line, so its amounts come from money.py even
    # for an old document whose stored totals predate it.
    totals = money.document_totals(items, rate, doc.get("rounding") or 0)

    original = None
    if doc.get("ref_doc_id"):
        o, _ = db.get_document(doc["ref_doc_id"])
        if o and o.get("user_id") == user_id:
            original = o

    return {"doc": doc, "items": items, "supplier": supplier, "buyer": buyer,
            "category": category, "rate": rate, "totals": totals, "original": original,
            "is_credit": doc["doc_type"] == "credit"}


def problems(doc_id):
    """What stops this document from being a valid e-invoice, in Latvian, for the user."""
    d = _get_einvoice_data(doc_id)
    sup, buy, out = d["supplier"], d["buyer"], []
    if not sup["name"]:
        out.append("Iestatījumos nav norādīts uzņēmuma nosaukums.")
    if not (_lv_reg(sup["reg"]) or (sup["vat_payer"] and sup["vat"])):
        out.append("Iestatījumos nav norādīts reģistrācijas numurs (vai personas kods), "
                   "pēc kura e-rēķinā identificē izrakstītāju.")
    if buy["person"]:
        out.append("Klients ir privātpersona: tai e-rēķins nav jāsūta, pietiek ar PDF.")
    elif not (_lv_reg(buy["reg"]) or VAT_SCHEMES.get(_vat_id(buy["vat"])[:2])):
        out.append("Klientam nav Latvijas reģistrācijas numura vai ES PVN numura, "
                   "kas kalpotu par e-rēķina adresi.")
    if d["category"] == "AE" and not (sup["vat"] and buy["vat"]):
        out.append("Nodokļa apgrieztajai maksāšanai vajag gan Jūsu, gan klienta PVN numuru.")
    if d["category"] in ("S", "Z") and not sup["vat"]:
        out.append("PVN maksātājam iestatījumos jānorāda PVN numurs.")
    if not d["items"]:
        out.append("Dokumentā nav rindu.")
    if (d["is_credit"] or d["doc"].get("ref_doc_id")) and not d["original"]:
        out.append("Nav atrodams rēķins, uz kuru šis dokuments atsaucas.")
    return out


def _party(parent, tag, party, category, is_supplier):
    wrap = SubElement(parent, f"{{{NS_CAC}}}{tag}")
    p = SubElement(wrap, f"{{{NS_CAC}}}Party")

    reg = "" if party["person"] else _lv_reg(party["reg"])
    vat = _vat_id(party["vat"]) if party["vat_payer"] or not is_supplier else ""
    vat_scheme = VAT_SCHEMES.get(vat[:2]) if vat else None
    # Electronic address: the registration number for a Latvian entity (that is
    # what e-adrese and VID file it under), else the VAT number. A self-employed
    # seller has no company number; their taxpayer code at VID is the personal
    # code, so that is their address. A private buyer gets none: they don't
    # need an e-invoice, and a personal code doesn't belong in one.
    person_code = _lv_reg(party["reg"]) if party["person"] and is_supplier else ""
    if reg or person_code:
        _text(p, "EndpointID", reg or person_code, schemeID=SCHEME_LV_REG)
    elif vat_scheme:
        _text(p, "EndpointID", vat, schemeID=vat_scheme)
    if reg:
        pid = SubElement(p, f"{{{NS_CAC}}}PartyIdentification")
        _text(pid, "ID", reg, schemeID=SCHEME_LV_REG)

    name = SubElement(p, f"{{{NS_CAC}}}PartyName")
    _text(name, "Name", party["name"] or "—")

    addr = SubElement(p, f"{{{NS_CAC}}}PostalAddress")
    if party["addr"]:
        _text(addr, "StreetName", party["addr"])
    country = SubElement(addr, f"{{{NS_CAC}}}Country")
    _text(country, "IdentificationCode", _country(party))

    # No VAT identifiers at all on an invoice outside the scope of VAT (BR-O-02)
    if vat and category != "O":
        ts = SubElement(p, f"{{{NS_CAC}}}PartyTaxScheme")
        _text(ts, "CompanyID", vat)
        scheme = SubElement(ts, f"{{{NS_CAC}}}TaxScheme")
        _text(scheme, "ID", "VAT")

    legal = SubElement(p, f"{{{NS_CAC}}}PartyLegalEntity")
    _text(legal, "RegistrationName", party["name"] or "—")
    if reg:
        _text(legal, "CompanyID", reg, schemeID=SCHEME_LV_REG)
    elif person_code:
        _text(legal, "CompanyID", person_code)

    if party["email"] or party["phone"]:
        contact = SubElement(p, f"{{{NS_CAC}}}Contact")
        if party["phone"]:
            _text(contact, "Telephone", party["phone"])
        if party["email"]:
            _text(contact, "ElectronicMail", party["email"])


def _tax_category(parent, tag, category, rate):
    cat = SubElement(parent, f"{{{NS_CAC}}}{tag}")
    _text(cat, "ID", category)
    if category != "O":
        _text(cat, "Percent", f"{money.dec(rate).normalize():f}")
    if tag == "TaxCategory":
        if category == "AE":
            _text(cat, "TaxExemptionReasonCode", "VATEX-EU-AE")
            _text(cat, "TaxExemptionReason", "Nodokļa apgrieztā maksāšana")
        elif category == "O":
            _text(cat, "TaxExemptionReasonCode", "VATEX-EU-O")
            _text(cat, "TaxExemptionReason", "Nav PVN maksātājs")
    scheme = SubElement(cat, f"{{{NS_CAC}}}TaxScheme")
    _text(scheme, "ID", "VAT")


def generate_einvoice_xml(doc_id):
    """(xml_string, filename) for a sales invoice, corrective invoice or credit note."""
    d = _get_einvoice_data(doc_id)
    doc, items, totals = d["doc"], d["items"], d["totals"]
    credit = d["is_credit"]
    ns = NS_CREDIT if credit else NS_INVOICE
    ET.register_namespace("", ns)
    root = Element(f"{{{ns}}}{'CreditNote' if credit else 'Invoice'}")

    _text(root, "CustomizationID", CUSTOMIZATION_ID)
    _text(root, "ProfileID", PROFILE_ID)
    _text(root, "ID", doc["doc_number"])
    _text(root, "IssueDate", doc["doc_date"])
    if not credit and doc.get("payment_due_date"):
        _text(root, "DueDate", doc["payment_due_date"])
    if credit:
        _text(root, "CreditNoteTypeCode", "381")
    else:
        # A corrective invoice is a commercial invoice that names the one it
        # replaces (BillingReference below): that reference is what VID reads.
        # PEPPOL keeps 384 for German parties only.
        _text(root, "InvoiceTypeCode", "380")
    if (doc.get("notes") or "").strip():
        _text(root, "Note", doc["notes"].strip())
    _text(root, "DocumentCurrencyCode", CURRENCY)
    # BuyerReference (or an order reference) is required; the buyer's own
    # registration number is what Latvian recipients route on
    # The buyer's own reference (a council routes on its school's code), else
    # their registration number; never a personal code
    buyer_reg = "" if d["buyer"]["person"] else d["buyer"]["reg"]
    _text(root, "BuyerReference", (doc.get("buyer_reference") or "").strip() or buyer_reg or doc["doc_number"])

    if d["original"]:
        ref = SubElement(root, f"{{{NS_CAC}}}BillingReference")
        inv = SubElement(ref, f"{{{NS_CAC}}}InvoiceDocumentReference")
        _text(inv, "ID", d["original"]["doc_number"])
        _text(inv, "IssueDate", d["original"]["doc_date"])

    _party(root, "AccountingSupplierParty", d["supplier"], d["category"], True)
    _party(root, "AccountingCustomerParty", d["buyer"], d["category"], False)

    account = re.sub(r"\s", "", d["supplier"]["account"])
    if not credit and account:
        pm = SubElement(root, f"{{{NS_CAC}}}PaymentMeans")
        _text(pm, "PaymentMeansCode", "30")  # credit transfer
        _text(pm, "PaymentID", doc["doc_number"])
        fa = SubElement(pm, f"{{{NS_CAC}}}PayeeFinancialAccount")
        _text(fa, "ID", account)
        if d["supplier"]["name"]:
            _text(fa, "Name", d["supplier"]["name"])
    if not credit:
        # An amount due needs a due date or payment terms (BR-CO-25), so an
        # invoice saved without a due date says so in words
        pt = SubElement(root, f"{{{NS_CAC}}}PaymentTerms")
        if doc.get("payment_due_date"):
            y, m, dd = doc["payment_due_date"].split("-")
            _text(pt, "Note", f"Apmaksāt līdz {dd}.{m}.{y}")
        else:
            _text(pt, "Note", "Apmaksas termiņš nav noteikts")

    tax = SubElement(root, f"{{{NS_CAC}}}TaxTotal")
    _amount(tax, "TaxAmount", totals["vat"])
    sub = SubElement(tax, f"{{{NS_CAC}}}TaxSubtotal")
    _amount(sub, "TaxableAmount", totals["subtotal"])
    _amount(sub, "TaxAmount", totals["vat"])
    _tax_category(sub, "TaxCategory", d["category"], d["rate"])

    lmt = SubElement(root, f"{{{NS_CAC}}}LegalMonetaryTotal")
    tax_inclusive = totals["subtotal"] + totals["vat"]
    _amount(lmt, "LineExtensionAmount", totals["subtotal"])
    _amount(lmt, "TaxExclusiveAmount", totals["subtotal"])
    _amount(lmt, "TaxInclusiveAmount", tax_inclusive)
    if totals["rounding"]:
        _amount(lmt, "PayableRoundingAmount", totals["rounding"])
    _amount(lmt, "PayableAmount", totals["total"])

    line_tag, qty_tag = ("CreditNoteLine", "CreditedQuantity") if credit else ("InvoiceLine", "InvoicedQuantity")
    for idx, (item, line) in enumerate(zip(items, totals["lines"]), 1):
        el = SubElement(root, f"{{{NS_CAC}}}{line_tag}")
        _text(el, "ID", idx)
        unit = item.get("unit") or "gab"
        qty, unit_price = money.dec(item["quantity"]), money.dec(item["price_per_unit"])
        if unit_price < 0:
            # A unit price can't be negative (BR-27): a discount line is a negative quantity
            qty, unit_price = -qty, -unit_price
        _text(el, qty_tag, _dec_text(qty), unitCode=_unit_code(unit))
        _amount(el, "LineExtensionAmount", line)
        it = SubElement(el, f"{{{NS_CAC}}}Item")
        _text(it, "Name", item.get("product_name") or item.get("description") or f"Pozīcija {idx}")
        _tax_category(it, "ClassifiedTaxCategory", d["category"], d["rate"])
        prop = SubElement(it, f"{{{NS_CAC}}}AdditionalItemProperty")
        _text(prop, "Name", "Mērvienība")
        _text(prop, "Value", unit)
        price = SubElement(el, f"{{{NS_CAC}}}Price")
        p = SubElement(price, f"{{{NS_CBC}}}PriceAmount")
        p.set("currencyID", CURRENCY)
        # "Included in the price" lines carry no amount; the quantity stays
        p.text = "0" if item.get("included_in_price") else _dec_text(unit_price)

    rough = tostring(root, encoding="unicode")
    pretty = parseString(rough).toprettyxml(indent="  ")
    xml_string = '<?xml version="1.0" encoding="UTF-8"?>\n' + pretty.split("\n", 1)[1].strip() + "\n"
    filename = f"{doc['doc_number'].replace('/', '_')}_e-rekins.xml"
    return xml_string, filename


def generate_einvoice_file(doc_id):
    """Write the e-invoice XML to a temp file. Returns (path, filename)."""
    xml_string, filename = generate_einvoice_xml(doc_id)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xml", mode="w", encoding="utf-8")
    tmp.write(xml_string)
    tmp.close()
    return tmp.name, filename
