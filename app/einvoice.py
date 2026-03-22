"""
E-invoice (e-rēķins) generator for V-Rēķini.
Generates PEPPOL BIS Billing 3.0 compliant UBL 2.1 XML invoices
conforming to LVS EN 16931-1:2017 (Latvian e-invoice standard).

Mandatory in Latvia from 2028.
Reference: https://docs.peppol.eu/poacc/billing/3.0/
"""

import os
import datetime
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

from app import database as db

# Register namespace prefixes so ElementTree uses cbc:/cac: instead of ns0:/ns1:
ET.register_namespace("", NS_INVOICE := "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2")
ET.register_namespace("cac", NS_CAC := "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2")
ET.register_namespace("cbc", NS_CBC := "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2")

# PEPPOL BIS 3.0 identifiers
CUSTOMIZATION_ID = "urn:cen.eu:en16931:2017#compliant#urn:fdc:peppol.eu:2017:poacc:billing:3.0"
PROFILE_ID = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"

# (Namespace constants NS_INVOICE, NS_CAC, NS_CBC defined above via register_namespace)

# Mapping from app unit names to UN/ECE Recommendation 20 codes
# https://docs.peppol.eu/poacc/billing/3.0/codelist/UNECERec20/
UNIT_CODE_MAP = {
    "kg": "KGM",       # kilogram
    "gab": "C62",      # piece / one (unit)
    "gab.": "C62",
    "kaste": "CT",      # carton
    "iepak.": "PK",     # package
    "l": "LTR",         # litre
    "h": "HUR",         # hour
    "m": "MTR",         # metre
    "m²": "MTK",        # square metre
    "m³": "MTQ",        # cubic metre
    "t": "TNE",         # tonne
    "km": "KMT",        # kilometre
    "diena": "DAY",     # day
    "dienas": "DAY",
    "kompl.": "SET",    # set
    "komplekts": "SET",
}

# Default currency
DEFAULT_CURRENCY = "EUR"
# Default country
DEFAULT_COUNTRY = "LV"


def _unit_code(unit_text):
    """Convert a Latvian unit name to UN/ECE Rec 20 code."""
    if not unit_text:
        return "C62"  # default: piece
    normalized = unit_text.strip().lower()
    return UNIT_CODE_MAP.get(normalized, "C62")


def _tax_category_id(vat_rate):
    """Determine the PEPPOL tax category ID based on VAT rate.
    S = Standard rate, Z = Zero rate, E = Exempt, O = Not subject to VAT.
    """
    if vat_rate is None or vat_rate == 0:
        return "Z"
    return "S"


def _fmt_amount(amount):
    """Format amount to 2 decimal places."""
    return f"{round(amount, 2):.2f}"


def _get_einvoice_data(doc_id):
    """Fetch all data needed for e-invoice generation (reuses PDF pattern)."""
    doc, items = db.get_document(doc_id)
    if not doc:
        raise ValueError(f"Dokuments ar ID {doc_id} nav atrasts")

    client = db.get_client(doc["client_id"])
    user_id = doc.get("user_id", 0)
    settings = db.get_all_user_settings(user_id) if user_id else db.get_all_settings()
    user = db.get_user(user_id) if user_id else {}

    def party_info(source_client, from_settings=False):
        if from_settings:
            return {
                "name": (settings.get("company_name", "") or "").strip(),
                "reg": (settings.get("reg_number", "") or "").strip(),
                "vat": (settings.get("vat_number", "") or "").strip(),
                "addr": (settings.get("legal_address", "") or "").strip(),
                "bank": (settings.get("bank_name", "") or "").strip(),
                "account": (settings.get("bank_account", "") or "").strip(),
                "email": ((user or {}).get("email", "") or "").strip(),
                "phone": ((user or {}).get("phone", "") or "").strip(),
                "contact": ((user or {}).get("display_name", "") or "").strip(),
            }
        return {
            "name": (source_client["name"] if source_client else "").strip(),
            "reg": ((source_client["reg_number"] or "") if source_client else "").strip(),
            "vat": ((source_client["vat_number"] or "") if source_client else "").strip(),
            "addr": ((source_client["legal_address"] or "") if source_client else "").strip(),
            "bank": ((source_client["bank_name"] or "") if source_client else "").strip(),
            "account": ((source_client["bank_account"] or "") if source_client else "").strip(),
            "email": ((source_client["email"] or "") if source_client else "").strip(),
            "phone": ((source_client["phone"] or "") if source_client else "").strip(),
            "contact": ((source_client["contact_person"] or "") if source_client else "").strip(),
        }

    if doc["doc_type"] == "buy":
        supplier = party_info(client)
        buyer = party_info(None, from_settings=True)
    else:
        supplier = party_info(None, from_settings=True)
        buyer = party_info(client)

    subtotal = sum(item["quantity"] * item["price_per_unit"] for item in items)
    vat_rate = doc["vat_rate"] or 0
    vat_amount = subtotal * (vat_rate / 100)
    total = subtotal + vat_amount

    return {
        "doc": doc,
        "items": items,
        "client": client,
        "settings": settings,
        "supplier": supplier,
        "buyer": buyer,
        "subtotal": subtotal,
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "total": total,
    }


def _add_party(parent_tag, parent_el, party, is_supplier=True):
    """Add AccountingSupplierParty or AccountingCustomerParty element."""
    party_wrapper = SubElement(parent_el, f"{{{NS_CAC}}}{parent_tag}")
    party_el = SubElement(party_wrapper, f"{{{NS_CAC}}}Party")

    # EndpointID — use VAT number or reg number as electronic address
    endpoint_id = party.get("vat") or party.get("reg") or "N/A"
    ep = SubElement(party_el, f"{{{NS_CBC}}}EndpointID")
    ep.set("schemeID", "9939")  # 9939 = LV national scheme
    ep.text = endpoint_id

    # PartyIdentification
    if party.get("reg"):
        party_id_wrapper = SubElement(party_el, f"{{{NS_CAC}}}PartyIdentification")
        party_id = SubElement(party_id_wrapper, f"{{{NS_CBC}}}ID")
        party_id.text = party["reg"]

    # PartyName
    party_name_wrapper = SubElement(party_el, f"{{{NS_CAC}}}PartyName")
    party_name = SubElement(party_name_wrapper, f"{{{NS_CBC}}}Name")
    party_name.text = party.get("name") or "N/A"

    # PostalAddress
    postal = SubElement(party_el, f"{{{NS_CAC}}}PostalAddress")
    if party.get("addr"):
        street = SubElement(postal, f"{{{NS_CBC}}}StreetName")
        street.text = party["addr"]
    country_el = SubElement(postal, f"{{{NS_CAC}}}Country")
    country_code = SubElement(country_el, f"{{{NS_CBC}}}IdentificationCode")
    country_code.text = DEFAULT_COUNTRY

    # PartyTaxScheme (VAT registration)
    if party.get("vat"):
        tax_scheme_wrapper = SubElement(party_el, f"{{{NS_CAC}}}PartyTaxScheme")
        company_id = SubElement(tax_scheme_wrapper, f"{{{NS_CBC}}}CompanyID")
        company_id.text = party["vat"]
        tax_scheme = SubElement(tax_scheme_wrapper, f"{{{NS_CAC}}}TaxScheme")
        tax_scheme_id = SubElement(tax_scheme, f"{{{NS_CBC}}}ID")
        tax_scheme_id.text = "VAT"

    # PartyLegalEntity
    legal = SubElement(party_el, f"{{{NS_CAC}}}PartyLegalEntity")
    reg_name = SubElement(legal, f"{{{NS_CBC}}}RegistrationName")
    reg_name.text = party.get("name") or "N/A"
    if party.get("reg"):
        company_id_legal = SubElement(legal, f"{{{NS_CBC}}}CompanyID")
        company_id_legal.text = party["reg"]

    # Contact (optional but useful — email and phone)
    if party.get("email") or party.get("phone") or party.get("contact"):
        contact_el = SubElement(party_el, f"{{{NS_CAC}}}Contact")
        if party.get("contact"):
            contact_name = SubElement(contact_el, f"{{{NS_CBC}}}Name")
            contact_name.text = party["contact"]
        if party.get("phone"):
            contact_phone = SubElement(contact_el, f"{{{NS_CBC}}}Telephone")
            contact_phone.text = party["phone"]
        if party.get("email"):
            contact_email = SubElement(contact_el, f"{{{NS_CBC}}}ElectronicMail")
            contact_email.text = party["email"]


def generate_einvoice_xml(doc_id):
    """Generate a PEPPOL BIS Billing 3.0 compliant UBL 2.1 XML invoice.

    Returns (xml_string, filename) tuple.
    """
    data = _get_einvoice_data(doc_id)
    doc = data["doc"]
    items = data["items"]
    supplier = data["supplier"]
    buyer = data["buyer"]

    currency = DEFAULT_CURRENCY

    # --- Root element (namespaces registered globally via ET.register_namespace) ---
    root = Element(f"{{{NS_INVOICE}}}Invoice")

    # --- Header fields ---
    cust_id = SubElement(root, f"{{{NS_CBC}}}CustomizationID")
    cust_id.text = CUSTOMIZATION_ID

    prof_id = SubElement(root, f"{{{NS_CBC}}}ProfileID")
    prof_id.text = PROFILE_ID

    inv_id = SubElement(root, f"{{{NS_CBC}}}ID")
    inv_id.text = doc["doc_number"]

    issue_date = SubElement(root, f"{{{NS_CBC}}}IssueDate")
    issue_date.text = doc["doc_date"]

    if doc.get("payment_due_date"):
        due_date = SubElement(root, f"{{{NS_CBC}}}DueDate")
        due_date.text = doc["payment_due_date"]

    inv_type = SubElement(root, f"{{{NS_CBC}}}InvoiceTypeCode")
    inv_type.text = "380"  # 380 = Commercial invoice

    doc_currency = SubElement(root, f"{{{NS_CBC}}}DocumentCurrencyCode")
    doc_currency.text = currency

    # BuyerReference — use buyer reg number or invoice number as fallback
    buyer_ref = SubElement(root, f"{{{NS_CBC}}}BuyerReference")
    buyer_ref.text = buyer.get("reg") or doc["doc_number"]

    # --- Parties ---
    _add_party("AccountingSupplierParty", root, supplier, is_supplier=True)
    _add_party("AccountingCustomerParty", root, buyer, is_supplier=False)

    # --- PaymentMeans ---
    if supplier.get("account"):
        payment_means = SubElement(root, f"{{{NS_CAC}}}PaymentMeans")
        payment_code = SubElement(payment_means, f"{{{NS_CBC}}}PaymentMeansCode")
        payment_code.text = "30"  # 30 = Credit transfer
        payment_id = SubElement(payment_means, f"{{{NS_CBC}}}PaymentID")
        payment_id.text = doc["doc_number"]
        fin_account = SubElement(payment_means, f"{{{NS_CAC}}}PayeeFinancialAccount")
        account_id = SubElement(fin_account, f"{{{NS_CBC}}}ID")
        account_id.text = supplier["account"]
        if supplier.get("bank"):
            account_name = SubElement(fin_account, f"{{{NS_CBC}}}Name")
            account_name.text = supplier["bank"]

    # --- PaymentTerms ---
    if doc.get("payment_due_date"):
        payment_terms = SubElement(root, f"{{{NS_CAC}}}PaymentTerms")
        note = SubElement(payment_terms, f"{{{NS_CBC}}}Note")
        note.text = f"Apmaksas termiņš: {doc['payment_due_date']}"

    # --- TaxTotal ---
    vat_rate = data["vat_rate"]
    vat_amount = data["vat_amount"]
    subtotal = data["subtotal"]
    total = data["total"]
    tax_cat_id = _tax_category_id(vat_rate)

    tax_total = SubElement(root, f"{{{NS_CAC}}}TaxTotal")
    tax_amount = SubElement(tax_total, f"{{{NS_CBC}}}TaxAmount")
    tax_amount.set("currencyID", currency)
    tax_amount.text = _fmt_amount(vat_amount)

    tax_subtotal = SubElement(tax_total, f"{{{NS_CAC}}}TaxSubtotal")
    taxable_amount = SubElement(tax_subtotal, f"{{{NS_CBC}}}TaxableAmount")
    taxable_amount.set("currencyID", currency)
    taxable_amount.text = _fmt_amount(subtotal)
    tax_sub_amount = SubElement(tax_subtotal, f"{{{NS_CBC}}}TaxAmount")
    tax_sub_amount.set("currencyID", currency)
    tax_sub_amount.text = _fmt_amount(vat_amount)

    tax_category = SubElement(tax_subtotal, f"{{{NS_CAC}}}TaxCategory")
    tax_cat = SubElement(tax_category, f"{{{NS_CBC}}}ID")
    tax_cat.text = tax_cat_id
    tax_pct = SubElement(tax_category, f"{{{NS_CBC}}}Percent")
    tax_pct.text = str(vat_rate)
    tax_scheme = SubElement(tax_category, f"{{{NS_CAC}}}TaxScheme")
    tax_scheme_id = SubElement(tax_scheme, f"{{{NS_CBC}}}ID")
    tax_scheme_id.text = "VAT"

    # --- LegalMonetaryTotal ---
    monetary = SubElement(root, f"{{{NS_CAC}}}LegalMonetaryTotal")

    line_ext = SubElement(monetary, f"{{{NS_CBC}}}LineExtensionAmount")
    line_ext.set("currencyID", currency)
    line_ext.text = _fmt_amount(subtotal)

    tax_excl = SubElement(monetary, f"{{{NS_CBC}}}TaxExclusiveAmount")
    tax_excl.set("currencyID", currency)
    tax_excl.text = _fmt_amount(subtotal)

    tax_incl = SubElement(monetary, f"{{{NS_CBC}}}TaxInclusiveAmount")
    tax_incl.set("currencyID", currency)
    tax_incl.text = _fmt_amount(total)

    payable = SubElement(monetary, f"{{{NS_CBC}}}PayableAmount")
    payable.set("currencyID", currency)
    payable.text = _fmt_amount(total)

    # --- InvoiceLines ---
    for idx, item in enumerate(items, 1):
        line_total = item["quantity"] * item["price_per_unit"]

        inv_line = SubElement(root, f"{{{NS_CAC}}}InvoiceLine")

        line_id = SubElement(inv_line, f"{{{NS_CBC}}}ID")
        line_id.text = str(idx)

        qty = SubElement(inv_line, f"{{{NS_CBC}}}InvoicedQuantity")
        unit_text = item.get("unit") or "gab"
        qty.set("unitCode", _unit_code(unit_text))
        qty.text = _fmt_amount(item["quantity"])

        line_ext_amount = SubElement(inv_line, f"{{{NS_CBC}}}LineExtensionAmount")
        line_ext_amount.set("currencyID", currency)
        line_ext_amount.text = _fmt_amount(line_total)

        # Item
        item_el = SubElement(inv_line, f"{{{NS_CAC}}}Item")
        item_name = SubElement(item_el, f"{{{NS_CBC}}}Name")
        item_name.text = item.get("product_name") or item.get("name") or f"Pozīcija {idx}"

        # AdditionalItemProperty — human-readable unit name
        if unit_text:
            add_prop = SubElement(item_el, f"{{{NS_CAC}}}AdditionalItemProperty")
            prop_name = SubElement(add_prop, f"{{{NS_CBC}}}Name")
            prop_name.text = "Mērvienība"
            prop_val = SubElement(add_prop, f"{{{NS_CBC}}}Value")
            prop_val.text = unit_text

        # ClassifiedTaxCategory
        classified_tax = SubElement(item_el, f"{{{NS_CAC}}}ClassifiedTaxCategory")
        cls_tax_id = SubElement(classified_tax, f"{{{NS_CBC}}}ID")
        cls_tax_id.text = tax_cat_id
        cls_tax_pct = SubElement(classified_tax, f"{{{NS_CBC}}}Percent")
        cls_tax_pct.text = str(vat_rate)
        cls_tax_scheme = SubElement(classified_tax, f"{{{NS_CAC}}}TaxScheme")
        cls_tax_scheme_id = SubElement(cls_tax_scheme, f"{{{NS_CBC}}}ID")
        cls_tax_scheme_id.text = "VAT"

        # Price
        price_el = SubElement(inv_line, f"{{{NS_CAC}}}Price")
        price_amount = SubElement(price_el, f"{{{NS_CBC}}}PriceAmount")
        price_amount.set("currencyID", currency)
        price_amount.text = _fmt_amount(item["price_per_unit"])

    # --- Serialize to pretty XML ---
    rough = tostring(root, encoding="unicode", xml_declaration=False)

    # Use minidom for pretty printing
    dom = parseString(f'<?xml version="1.0" encoding="UTF-8"?>\n{rough}')
    xml_string = dom.toprettyxml(indent="  ", encoding=None)
    # Remove extra xml declaration added by toprettyxml (we added our own)
    if xml_string.startswith('<?xml'):
        xml_string = xml_string.split('\n', 1)[1] if '\n' in xml_string else xml_string
    xml_string = f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_string.strip()}'

    filename = f"{doc['doc_number'].replace('/', '_')}_e-rekins.xml"

    return xml_string, filename


def generate_einvoice_file(doc_id):
    """Generate e-invoice XML and save to a temp file. Returns file path."""
    import tempfile
    xml_string, filename = generate_einvoice_xml(doc_id)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xml", mode="w", encoding="utf-8")
    tmp.write(xml_string)
    tmp.close()
    return tmp.name, filename
