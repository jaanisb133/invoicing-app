"""
PDF invoice generation for Pavadzīmju Pārvaldnieks (Web).
Adapted from desktop/pdf_generator.py with 3 professional templates.
Uses reportlab for PDF creation with Latvian character support.
"""

import os
import sys
import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

from app import database as db

# Available templates
TEMPLATES = {
    "classic": "Klasiskā",
    "modern": "Modernā",
    "minimal": "Minimālā",
}


def _get_font_path(filename):
    """Find font file across different OS locations."""
    app_dir = os.path.dirname(os.path.abspath(__file__))
    search_paths = [
        os.path.join(app_dir, "fonts"),
        "/usr/share/fonts/truetype/dejavu",
        "/usr/local/share/fonts",
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"),
    ]
    for path in search_paths:
        full = os.path.join(path, filename)
        if os.path.exists(full):
            return full
    return None


def _register_fonts():
    """Register fonts with Latvian character support."""
    from reportlab.pdfbase.pdfmetrics import registerFontFamily

    font_options = [
        ("Arial", "arial.ttf", "Arial-Bold", "arialbd.ttf"),
        ("DejaVu", "DejaVuSans.ttf", "DejaVu-Bold", "DejaVuSans-Bold.ttf"),
    ]

    for font_name, font_file, bold_name, bold_file in font_options:
        try:
            pdfmetrics.getFont(font_name)
            return font_name, bold_name
        except KeyError:
            regular_path = _get_font_path(font_file)
            bold_path = _get_font_path(bold_file)
            if regular_path and bold_path:
                pdfmetrics.registerFont(TTFont(font_name, regular_path))
                pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                registerFontFamily(font_name, normal=font_name, bold=bold_name)
                return font_name, bold_name

    return "Helvetica", "Helvetica-Bold"


def get_output_dir():
    app_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(os.path.dirname(app_dir), "data", "dokumenti")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def _get_doc_data(doc_id):
    """Fetch all data needed for invoice generation."""
    doc, items = db.get_document(doc_id)
    if not doc:
        raise ValueError(f"Dokuments ar ID {doc_id} nav atrasts")

    client = db.get_client(doc["client_id"])
    settings = db.get_all_settings()

    # Format date
    raw_date = doc["doc_date"]
    try:
        if isinstance(raw_date, str):
            d = datetime.date.fromisoformat(raw_date)
        else:
            d = raw_date
        display_date = d.strftime("%d.%m.%Y")
    except Exception:
        display_date = raw_date

    # Document type label
    if doc["doc_type"] == "buy":
        doc_type_label = settings.get("buy_doc_name", "PIRKUMA PAVADZĪME")
    else:
        doc_type_label = settings.get("sell_doc_name", "PĀRDOŠANAS PAVADZĪME")

    # Party info
    def party_info(source_client, from_settings=False):
        if from_settings:
            return {
                "name": settings.get("company_name", ""),
                "reg": settings.get("reg_number", ""),
                "vat": settings.get("vat_number", ""),
                "addr": settings.get("legal_address", ""),
                "bank": settings.get("bank_name", ""),
                "account": settings.get("bank_account", ""),
            }
        return {
            "name": source_client["name"] if source_client else "",
            "reg": (source_client["reg_number"] or "") if source_client else "",
            "vat": (source_client["vat_number"] or "") if source_client else "",
            "addr": (source_client["legal_address"] or "") if source_client else "",
            "bank": (source_client["bank_name"] or "") if source_client else "",
            "account": (source_client["bank_account"] or "") if source_client else "",
        }

    if doc["doc_type"] == "buy":
        supplier = party_info(client)
        buyer = party_info(None, from_settings=True)
    else:
        supplier = party_info(None, from_settings=True)
        buyer = party_info(client)

    # Calculate totals
    subtotal = 0
    for item in items:
        subtotal += item["quantity"] * item["price_per_unit"]
    vat_rate = doc["vat_rate"]
    vat_amount = subtotal * (vat_rate / 100)
    total = subtotal + vat_amount

    return {
        "doc": doc,
        "items": items,
        "client": client,
        "settings": settings,
        "display_date": display_date,
        "doc_type_label": doc_type_label,
        "supplier": supplier,
        "buyer": buyer,
        "subtotal": subtotal,
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "total": total,
    }


def generate_invoice_pdf(doc_id, template="classic"):
    """Generate a PDF invoice using the specified template."""
    if template not in TEMPLATES:
        template = "classic"

    generators = {
        "classic": _generate_classic,
        "modern": _generate_modern,
        "minimal": _generate_minimal,
    }
    return generators[template](doc_id)


# =============================================================================
# Template 1: Classic — Traditional Latvian business invoice
# =============================================================================

def _generate_classic(doc_id):
    FONT, FONT_BOLD = _register_fonts()
    data = _get_doc_data(doc_id)
    doc = data["doc"]

    output_dir = get_output_dir()
    filename = f"{doc['doc_number']}.pdf"
    filepath = os.path.join(output_dir, filename)

    pdf = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm
    )

    title_style = ParagraphStyle(
        'InvoiceTitle', fontSize=16, alignment=TA_CENTER, spaceAfter=6 * mm,
        fontName=FONT_BOLD, leading=20
    )
    doc_num_style = ParagraphStyle(
        'DocNum', fontSize=12, alignment=TA_CENTER, spaceAfter=8 * mm,
        fontName=FONT, leading=16
    )
    normal = ParagraphStyle('N', fontSize=10, leading=14, fontName=FONT)
    bold = ParagraphStyle('B', fontSize=10, leading=14, fontName=FONT_BOLD)

    elements = []

    # Title
    elements.append(Paragraph(data["doc_type_label"], title_style))
    elements.append(Paragraph(f"Nr. {doc['doc_number']}", doc_num_style))
    elements.append(Paragraph(f"Datums: {data['display_date']}", bold))
    elements.append(Spacer(1, 4 * mm))

    # Parties table
    field_labels = [
        ("Nosaukums", "name"), ("Reģ.Nr.", "reg"), ("PVN Nr.", "vat"),
        ("Adrese", "addr"), ("Banka", "bank"), ("Konts", "account"),
    ]

    parties_data = [[
        Paragraph(f"<font name='{FONT_BOLD}'>Piegādātājs (Pārdevējs)</font>", normal),
        Paragraph(f"<font name='{FONT_BOLD}'>Pircējs</font>", normal),
    ]]
    for label, key in field_labels:
        parties_data.append([
            Paragraph(f"{label}: {data['supplier'][key]}", normal),
            Paragraph(f"{label}: {data['buyer'][key]}", normal),
        ])

    parties_table = Table(parties_data, colWidths=[85 * mm, 85 * mm])
    parties_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, colors.black),
    ]))
    elements.append(parties_table)
    elements.append(Spacer(1, 6 * mm))

    # Items table
    items_data = [[
        Paragraph(f"<font name='{FONT_BOLD}'>Nr.</font>", normal),
        Paragraph(f"<font name='{FONT_BOLD}'>Nosaukums</font>", normal),
        Paragraph(f"<font name='{FONT_BOLD}'>Mērv.</font>", normal),
        Paragraph(f"<font name='{FONT_BOLD}'>Daudzums</font>", normal),
        Paragraph(f"<font name='{FONT_BOLD}'>Cena</font>", normal),
        Paragraph(f"<font name='{FONT_BOLD}'>Summa</font>", normal),
    ]]

    for i, item in enumerate(data["items"], 1):
        line_total = item["quantity"] * item["price_per_unit"]
        items_data.append([
            Paragraph(str(i), normal),
            Paragraph(item["product_name"], normal),
            Paragraph(item["unit"], normal),
            Paragraph(f"{item['quantity']:.2f}", normal),
            Paragraph(f"{item['price_per_unit']:.2f}", normal),
            Paragraph(f"{line_total:.2f}", normal),
        ])

    num_items = len(data["items"])
    items_data.append(["", "", "", "",
                       Paragraph(f"<font name='{FONT_BOLD}'>Summa bez PVN:</font>", normal),
                       Paragraph(f"<font name='{FONT_BOLD}'>{data['subtotal']:.2f}</font>", normal)])
    items_data.append(["", "", "", "",
                       Paragraph(f"<font name='{FONT_BOLD}'>PVN ({data['vat_rate']:.0f}%):</font>", normal),
                       Paragraph(f"<font name='{FONT_BOLD}'>{data['vat_amount']:.2f}</font>", normal)])
    items_data.append(["", "", "", "",
                       Paragraph(f"<font name='{FONT_BOLD}'>Kopā ar PVN:</font>", normal),
                       Paragraph(f"<font name='{FONT_BOLD}'>{data['total']:.2f}</font>", normal)])

    col_widths = [10 * mm, 60 * mm, 20 * mm, 25 * mm, 25 * mm, 30 * mm]
    items_table = Table(items_data, colWidths=col_widths)
    items_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, num_items), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.9, 0.9, 0.9)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    elements.append(items_table)

    if doc["notes"]:
        elements.append(Spacer(1, 6 * mm))
        elements.append(Paragraph(f"Piezīmes: {doc['notes']}", normal))

    elements.append(Spacer(1, 15 * mm))
    sig_data = [[
        Paragraph(f"<font name='{FONT_BOLD}'>Izsniedza:</font> ____________________", normal),
        Paragraph(f"<font name='{FONT_BOLD}'>Saņēma:</font> ____________________", normal),
    ]]
    elements.append(Table(sig_data, colWidths=[85 * mm, 85 * mm]))

    pdf.build(elements)
    return filepath


# =============================================================================
# Template 2: Modern — Clean design with accent color and structured layout
# =============================================================================

def _generate_modern(doc_id):
    FONT, FONT_BOLD = _register_fonts()
    data = _get_doc_data(doc_id)
    doc = data["doc"]

    output_dir = get_output_dir()
    filename = f"{doc['doc_number']}.pdf"
    filepath = os.path.join(output_dir, filename)

    accent = colors.Color(0.15, 0.30, 0.55)  # Deep blue
    accent_light = colors.Color(0.92, 0.95, 0.98)
    gray_line = colors.Color(0.80, 0.80, 0.80)

    pdf = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm
    )

    styles = {
        "title": ParagraphStyle('Title', fontSize=20, fontName=FONT_BOLD,
                                textColor=accent, leading=24, spaceAfter=2 * mm),
        "doc_num": ParagraphStyle('DocNum', fontSize=11, fontName=FONT,
                                  textColor=colors.Color(0.4, 0.4, 0.4), leading=14),
        "section": ParagraphStyle('Section', fontSize=9, fontName=FONT_BOLD,
                                  textColor=accent, leading=12, spaceAfter=1 * mm,
                                  spaceBefore=3 * mm),
        "normal": ParagraphStyle('N', fontSize=9, leading=13, fontName=FONT),
        "bold": ParagraphStyle('B', fontSize=9, leading=13, fontName=FONT_BOLD),
        "small": ParagraphStyle('S', fontSize=8, leading=11, fontName=FONT,
                                textColor=colors.Color(0.45, 0.45, 0.45)),
        "total_label": ParagraphStyle('TL', fontSize=10, leading=13,
                                      fontName=FONT_BOLD, alignment=TA_RIGHT),
        "total_value": ParagraphStyle('TV', fontSize=10, leading=13,
                                      fontName=FONT_BOLD, alignment=TA_RIGHT, textColor=accent),
        "grand_total": ParagraphStyle('GT', fontSize=13, leading=16,
                                      fontName=FONT_BOLD, alignment=TA_RIGHT, textColor=accent),
    }

    elements = []

    # Header: Title + doc number + date on the right
    header_data = [[
        Paragraph(data["doc_type_label"], styles["title"]),
        Paragraph(f"Nr. {doc['doc_number']}<br/>Datums: {data['display_date']}", styles["doc_num"]),
    ]]
    header_table = Table(header_data, colWidths=[110 * mm, 64 * mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(HRFlowable(width="100%", thickness=2, color=accent, spaceAfter=4 * mm))

    # Parties - side by side boxes
    elements.append(Paragraph("PIEGĀDĀTĀJS / PĀRDEVĒJS", styles["section"]))
    supplier_lines = [
        f"<font name='{FONT_BOLD}'>{data['supplier']['name']}</font>",
        f"Reģ.Nr.: {data['supplier']['reg']}" if data['supplier']['reg'] else "",
        f"PVN Nr.: {data['supplier']['vat']}" if data['supplier']['vat'] else "",
        f"{data['supplier']['addr']}" if data['supplier']['addr'] else "",
        f"Banka: {data['supplier']['bank']}" if data['supplier']['bank'] else "",
        f"Konts: {data['supplier']['account']}" if data['supplier']['account'] else "",
    ]
    buyer_lines = [
        f"<font name='{FONT_BOLD}'>{data['buyer']['name']}</font>",
        f"Reģ.Nr.: {data['buyer']['reg']}" if data['buyer']['reg'] else "",
        f"PVN Nr.: {data['buyer']['vat']}" if data['buyer']['vat'] else "",
        f"{data['buyer']['addr']}" if data['buyer']['addr'] else "",
        f"Banka: {data['buyer']['bank']}" if data['buyer']['bank'] else "",
        f"Konts: {data['buyer']['account']}" if data['buyer']['account'] else "",
    ]

    party_data = [[
        [Paragraph("PIEGĀDĀTĀJS", styles["section"])] +
        [Paragraph(l, styles["normal"]) for l in supplier_lines if l],
        [Paragraph("PIRCĒJS", styles["section"])] +
        [Paragraph(l, styles["normal"]) for l in buyer_lines if l],
    ]]
    # Flatten into separate rows for proper rendering
    max_rows = max(len([l for l in supplier_lines if l]), len([l for l in buyer_lines if l])) + 1
    s_items = [Paragraph("PIEGĀDĀTĀJS", styles["section"])] + [Paragraph(l, styles["normal"]) for l in supplier_lines if l]
    b_items = [Paragraph("PIRCĒJS", styles["section"])] + [Paragraph(l, styles["normal"]) for l in buyer_lines if l]

    party_rows = []
    for i in range(max(len(s_items), len(b_items))):
        party_rows.append([
            s_items[i] if i < len(s_items) else "",
            b_items[i] if i < len(b_items) else "",
        ])

    party_table = Table(party_rows, colWidths=[87 * mm, 87 * mm])
    party_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (0, 0), (0, -1), 0),
        ('LEFTPADDING', (1, 0), (1, -1), 8 * mm),
        ('LINEBELOW', (0, 0), (0, 0), 0.5, accent),
        ('LINEBELOW', (1, 0), (1, 0), 0.5, accent),
    ]))
    elements.append(party_table)
    elements.append(Spacer(1, 5 * mm))

    # Items table - modern style
    th = ParagraphStyle('TH', fontSize=8, fontName=FONT_BOLD, textColor=colors.white, leading=11)
    td = ParagraphStyle('TD', fontSize=9, leading=12, fontName=FONT)
    td_r = ParagraphStyle('TDR', fontSize=9, leading=12, fontName=FONT, alignment=TA_RIGHT)

    items_data = [[
        Paragraph("Nr.", th),
        Paragraph("Nosaukums", th),
        Paragraph("Mērvienība", th),
        Paragraph("Daudzums", th),
        Paragraph("Cena (EUR)", th),
        Paragraph("Summa (EUR)", th),
    ]]

    for i, item in enumerate(data["items"], 1):
        line_total = item["quantity"] * item["price_per_unit"]
        items_data.append([
            Paragraph(str(i), td),
            Paragraph(item["product_name"], td),
            Paragraph(item["unit"], td),
            Paragraph(f"{item['quantity']:.2f}", td_r),
            Paragraph(f"{item['price_per_unit']:.2f}", td_r),
            Paragraph(f"{line_total:.2f}", td_r),
        ])

    num_items = len(data["items"])
    col_widths = [10 * mm, 62 * mm, 18 * mm, 22 * mm, 28 * mm, 28 * mm]
    items_table = Table(items_data, colWidths=col_widths)

    style_commands = [
        ('BACKGROUND', (0, 0), (-1, 0), accent),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, 0), 1, accent),
    ]
    for row in range(1, num_items + 1):
        if row % 2 == 0:
            style_commands.append(('BACKGROUND', (0, row), (-1, row), accent_light))
        style_commands.append(('LINEBELOW', (0, row), (-1, row), 0.5, gray_line))

    items_table.setStyle(TableStyle(style_commands))
    elements.append(items_table)
    elements.append(Spacer(1, 4 * mm))

    # Totals - right aligned
    totals_data = [
        [Paragraph("Summa bez PVN:", styles["total_label"]),
         Paragraph(f"EUR {data['subtotal']:.2f}", styles["total_value"])],
        [Paragraph(f"PVN ({data['vat_rate']:.0f}%):", styles["total_label"]),
         Paragraph(f"EUR {data['vat_amount']:.2f}", styles["total_value"])],
        [Paragraph("KOPĀ AR PVN:", styles["total_label"]),
         Paragraph(f"EUR {data['total']:.2f}", styles["grand_total"])],
    ]
    totals_table = Table(totals_data, colWidths=[130 * mm, 40 * mm])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEABOVE', (0, 2), (-1, 2), 1, accent),
    ]))
    elements.append(totals_table)

    if doc["notes"]:
        elements.append(Spacer(1, 5 * mm))
        elements.append(Paragraph(f"<font name='{FONT_BOLD}'>Piezīmes:</font> {doc['notes']}",
                                  styles["normal"]))

    elements.append(Spacer(1, 15 * mm))
    sig_data = [[
        Paragraph(f"<font name='{FONT_BOLD}'>Izsniedza:</font>", styles["normal"]),
        Paragraph("_________________________", styles["normal"]),
        Paragraph(f"<font name='{FONT_BOLD}'>Saņēma:</font>", styles["normal"]),
        Paragraph("_________________________", styles["normal"]),
    ]]
    sig_table = Table(sig_data, colWidths=[22 * mm, 60 * mm, 20 * mm, 60 * mm])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('ALIGN', (1, 0), (1, 0), 'LEFT'),
        ('ALIGN', (3, 0), (3, 0), 'LEFT'),
    ]))
    elements.append(sig_table)

    pdf.build(elements)
    return filepath


# =============================================================================
# Template 3: Minimal — Clean and understated design
# =============================================================================

def _generate_minimal(doc_id):
    FONT, FONT_BOLD = _register_fonts()
    data = _get_doc_data(doc_id)
    doc = data["doc"]

    output_dir = get_output_dir()
    filename = f"{doc['doc_number']}.pdf"
    filepath = os.path.join(output_dir, filename)

    dark = colors.Color(0.2, 0.2, 0.2)
    mid = colors.Color(0.5, 0.5, 0.5)
    light_bg = colors.Color(0.96, 0.96, 0.96)
    border = colors.Color(0.85, 0.85, 0.85)

    pdf = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=25 * mm, rightMargin=25 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm
    )

    styles = {
        "title": ParagraphStyle('Title', fontSize=14, fontName=FONT_BOLD,
                                textColor=dark, leading=18, spaceAfter=1 * mm),
        "subtitle": ParagraphStyle('Sub', fontSize=10, fontName=FONT,
                                   textColor=mid, leading=13, spaceAfter=6 * mm),
        "label": ParagraphStyle('Label', fontSize=7.5, fontName=FONT_BOLD,
                                textColor=mid, leading=10, spaceBefore=0),
        "value": ParagraphStyle('Value', fontSize=9, fontName=FONT,
                                textColor=dark, leading=12),
        "normal": ParagraphStyle('N', fontSize=9, leading=12, fontName=FONT, textColor=dark),
        "bold": ParagraphStyle('B', fontSize=9, leading=12, fontName=FONT_BOLD, textColor=dark),
    }

    elements = []

    # Header
    elements.append(Paragraph(data["doc_type_label"], styles["title"]))
    elements.append(Paragraph(
        f"Nr. {doc['doc_number']}  &nbsp;&nbsp;|&nbsp;&nbsp;  {data['display_date']}",
        styles["subtitle"]
    ))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=border, spaceAfter=5 * mm))

    # Parties - compact two-column
    def _party_block(title, info):
        lines = [Paragraph(title, styles["label"])]
        lines.append(Paragraph(f"<font name='{FONT_BOLD}'>{info['name']}</font>", styles["value"]))
        if info['reg']:
            lines.append(Paragraph(f"Reģ.Nr. {info['reg']}", styles["value"]))
        if info['vat']:
            lines.append(Paragraph(f"PVN {info['vat']}", styles["value"]))
        if info['addr']:
            lines.append(Paragraph(info['addr'], styles["value"]))
        if info['bank'] or info['account']:
            bank_line = ""
            if info['bank']:
                bank_line += info['bank']
            if info['account']:
                bank_line += f"  |  {info['account']}"
            lines.append(Paragraph(bank_line, styles["value"]))
        return lines

    s_block = _party_block("PIEGĀDĀTĀJS", data["supplier"])
    b_block = _party_block("PIRCĒJS", data["buyer"])

    party_rows = []
    for i in range(max(len(s_block), len(b_block))):
        party_rows.append([
            s_block[i] if i < len(s_block) else "",
            b_block[i] if i < len(b_block) else "",
        ])

    party_table = Table(party_rows, colWidths=[80 * mm, 80 * mm])
    party_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 0.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),
        ('LEFTPADDING', (1, 0), (1, -1), 10 * mm),
    ]))
    elements.append(party_table)
    elements.append(Spacer(1, 6 * mm))

    # Items table - minimal borders
    th = ParagraphStyle('TH', fontSize=7.5, fontName=FONT_BOLD, textColor=mid, leading=10)
    td = ParagraphStyle('TD', fontSize=9, leading=12, fontName=FONT, textColor=dark)
    td_r = ParagraphStyle('TDR', fontSize=9, leading=12, fontName=FONT,
                          textColor=dark, alignment=TA_RIGHT)

    items_data = [[
        Paragraph("#", th),
        Paragraph("PRECE", th),
        Paragraph("MĒRV.", th),
        Paragraph("DAUDZ.", th),
        Paragraph("CENA", th),
        Paragraph("SUMMA", th),
    ]]

    for i, item in enumerate(data["items"], 1):
        line_total = item["quantity"] * item["price_per_unit"]
        items_data.append([
            Paragraph(str(i), td),
            Paragraph(item["product_name"], td),
            Paragraph(item["unit"], td),
            Paragraph(f"{item['quantity']:.2f}", td_r),
            Paragraph(f"{item['price_per_unit']:.2f}", td_r),
            Paragraph(f"{line_total:.2f}", td_r),
        ])

    num_items = len(data["items"])
    col_widths = [8 * mm, 62 * mm, 16 * mm, 20 * mm, 25 * mm, 25 * mm]
    items_table = Table(items_data, colWidths=col_widths)

    style_cmds = [
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, mid),
        ('LINEBELOW', (0, num_items), (-1, num_items), 0.5, mid),
    ]
    for row in range(1, num_items + 1):
        style_cmds.append(('LINEBELOW', (0, row), (-1, row), 0.25, border))

    items_table.setStyle(TableStyle(style_cmds))
    elements.append(items_table)
    elements.append(Spacer(1, 4 * mm))

    # Totals - right-aligned, minimal
    tr = ParagraphStyle('TR', fontSize=9, leading=12, fontName=FONT,
                        textColor=mid, alignment=TA_RIGHT)
    tr_bold = ParagraphStyle('TRB', fontSize=10, leading=14, fontName=FONT_BOLD,
                             textColor=dark, alignment=TA_RIGHT)

    totals_data = [
        [Paragraph("Bez PVN", tr), Paragraph(f"{data['subtotal']:.2f} EUR", tr)],
        [Paragraph(f"PVN {data['vat_rate']:.0f}%", tr),
         Paragraph(f"{data['vat_amount']:.2f} EUR", tr)],
        [Paragraph("Kopā", tr_bold), Paragraph(f"{data['total']:.2f} EUR", tr_bold)],
    ]
    totals_table = Table(totals_data, colWidths=[120 * mm, 36 * mm])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LINEABOVE', (1, 2), (1, 2), 0.5, dark),
    ]))
    elements.append(totals_table)

    if doc["notes"]:
        elements.append(Spacer(1, 5 * mm))
        elements.append(HRFlowable(width="100%", thickness=0.25, color=border, spaceAfter=2 * mm))
        elements.append(Paragraph(f"Piezīmes: {doc['notes']}", styles["normal"]))

    elements.append(Spacer(1, 18 * mm))
    sig = ParagraphStyle('Sig', fontSize=8, leading=11, fontName=FONT, textColor=mid)
    sig_data = [[
        Paragraph("Izsniedza  ________________________", sig),
        Paragraph("Saņēma  ________________________", sig),
    ]]
    elements.append(Table(sig_data, colWidths=[80 * mm, 80 * mm]))

    pdf.build(elements)
    return filepath
