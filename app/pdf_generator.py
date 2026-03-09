"""
PDF invoice generation for V-Rēķini (Web).
Three professional templates using Liberation Sans for clean Latvian typography.
"""

import os
import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image
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

# --- Colour palette (matches the web UI monochrome theme) ---
C_BLACK = colors.Color(0.067, 0.094, 0.153)       # #111827
C_DARK = colors.Color(0.122, 0.161, 0.216)         # #1f2937
C_GRAY = colors.Color(0.216, 0.255, 0.318)         # #374151
C_MID = colors.Color(0.420, 0.447, 0.502)          # #6b7280
C_SILVER = colors.Color(0.612, 0.639, 0.686)       # #9ca3af
C_BORDER = colors.Color(0.898, 0.906, 0.922)       # #e5e7eb
C_LIGHT_BG = colors.Color(0.976, 0.980, 0.984)     # #f9fafb
C_WHITE = colors.white


def _get_font_path(filename):
    """Find font file across different OS locations."""
    app_dir = os.path.dirname(os.path.abspath(__file__))
    search_paths = [
        os.path.join(app_dir, "fonts"),
        "/usr/share/fonts/truetype/liberation",
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
    """Register fonts with Latvian character support.
    Prefers Liberation Sans (clean, professional, metrically-compatible with Arial).
    Falls back to DejaVu Sans, then Helvetica.
    """
    from reportlab.pdfbase.pdfmetrics import registerFontFamily

    font_options = [
        ("Liberation", "LiberationSans-Regular.ttf", "Liberation-Bold", "LiberationSans-Bold.ttf"),
        ("DejaVu", "DejaVuSans.ttf", "DejaVu-Bold", "DejaVuSans-Bold.ttf"),
        ("Arial", "arial.ttf", "Arial-Bold", "arialbd.ttf"),
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


def _get_logo_path(user_id):
    app_dir = os.path.dirname(os.path.abspath(__file__))
    logo_dir = os.path.join(os.path.dirname(app_dir), "data", "logos")
    filename = db.get_user_setting(user_id, "logo_filename")
    if filename:
        path = os.path.join(logo_dir, filename)
        if os.path.exists(path):
            return path
    return None


def _make_logo_element(logo_path, max_width=40*mm, max_height=20*mm):
    try:
        img = Image(logo_path)
        w, h = img.drawWidth, img.drawHeight
        if w > 0 and h > 0:
            ratio = min(max_width / w, max_height / h)
            img.drawWidth = w * ratio
            img.drawHeight = h * ratio
        return img
    except Exception:
        return None


def _get_doc_data(doc_id):
    """Fetch all data needed for invoice generation."""
    doc, items = db.get_document(doc_id)
    if not doc:
        raise ValueError(f"Dokuments ar ID {doc_id} nav atrasts")

    client = db.get_client(doc["client_id"])
    user_id = doc.get("user_id", 0)
    settings = db.get_all_user_settings(user_id) if user_id else db.get_all_settings()

    raw_date = doc["doc_date"]
    try:
        if isinstance(raw_date, str):
            d = datetime.date.fromisoformat(raw_date)
        else:
            d = raw_date
        display_date = d.strftime("%d.%m.%Y")
    except Exception:
        display_date = raw_date

    if doc["doc_type"] == "buy":
        doc_type_label = settings.get("buy_doc_name", "PIRKUMA PAVADZĪME")
    else:
        doc_type_label = settings.get("sell_doc_name", "PĀRDOŠANAS PAVADZĪME")

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

    subtotal = sum(item["quantity"] * item["price_per_unit"] for item in items)
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
    if template not in TEMPLATES:
        template = "classic"
    generators = {
        "classic": _generate_classic,
        "modern": _generate_modern,
        "minimal": _generate_minimal,
    }
    return generators[template](doc_id)


def _party_lines(info, FONT_BOLD, style):
    """Build a list of Paragraph elements for a party info block."""
    lines = []
    lines.append(Paragraph(f"<font name='{FONT_BOLD}'>{info['name']}</font>", style))
    if info['reg']:
        lines.append(Paragraph(f"Reģ.Nr.: {info['reg']}", style))
    if info['vat']:
        lines.append(Paragraph(f"PVN Nr.: {info['vat']}", style))
    if info['addr']:
        lines.append(Paragraph(info['addr'], style))
    if info['bank']:
        lines.append(Paragraph(f"Banka: {info['bank']}", style))
    if info['account']:
        lines.append(Paragraph(f"Konts: {info['account']}", style))
    return lines


# =============================================================================
# Template 1: Classic — Traditional, formal Latvian business invoice
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
        topMargin=18 * mm, bottomMargin=15 * mm
    )

    title_style = ParagraphStyle(
        'InvoiceTitle', fontSize=15, alignment=TA_CENTER, spaceAfter=2 * mm,
        fontName=FONT_BOLD, leading=19, textColor=C_BLACK
    )
    doc_num_style = ParagraphStyle(
        'DocNum', fontSize=11, alignment=TA_CENTER, spaceAfter=2 * mm,
        fontName=FONT, leading=14, textColor=C_GRAY
    )
    date_style = ParagraphStyle(
        'Date', fontSize=10, alignment=TA_CENTER, spaceAfter=8 * mm,
        fontName=FONT, leading=13, textColor=C_MID
    )
    normal = ParagraphStyle('N', fontSize=9.5, leading=14, fontName=FONT, textColor=C_BLACK)
    bold = ParagraphStyle('B', fontSize=9.5, leading=14, fontName=FONT_BOLD, textColor=C_BLACK)
    section_label = ParagraphStyle('SL', fontSize=8, leading=11, fontName=FONT_BOLD,
                                   textColor=C_MID, spaceAfter=1 * mm)

    elements = []

    # Logo
    logo_path = _get_logo_path(doc.get("user_id", 0))
    if logo_path:
        logo_el = _make_logo_element(logo_path, max_width=42*mm, max_height=21*mm)
        if logo_el:
            elements.append(logo_el)
            elements.append(Spacer(1, 4 * mm))

    # Title block
    elements.append(Paragraph(data["doc_type_label"], title_style))
    elements.append(Paragraph(f"Nr. {doc['doc_number']}", doc_num_style))
    elements.append(Paragraph(f"Datums: {data['display_date']}", date_style))

    # Thin divider
    elements.append(HRFlowable(width="100%", thickness=0.5, color=C_BORDER, spaceAfter=6 * mm))

    # Parties
    s_lines = [Paragraph("PIEGĀDĀTĀJS / PĀRDEVĒJS", section_label)] + \
              _party_lines(data['supplier'], FONT_BOLD, normal)
    b_lines = [Paragraph("PIRCĒJS", section_label)] + \
              _party_lines(data['buyer'], FONT_BOLD, normal)

    party_rows = []
    for i in range(max(len(s_lines), len(b_lines))):
        party_rows.append([
            s_lines[i] if i < len(s_lines) else "",
            b_lines[i] if i < len(b_lines) else "",
        ])

    parties_table = Table(party_rows, colWidths=[85 * mm, 85 * mm])
    parties_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (1, 0), (1, -1), 6 * mm),
    ]))
    elements.append(parties_table)
    elements.append(Spacer(1, 7 * mm))

    # Items table
    th = ParagraphStyle('TH', fontSize=8.5, fontName=FONT_BOLD, textColor=C_DARK, leading=11)
    td = ParagraphStyle('TD', fontSize=9.5, leading=13, fontName=FONT, textColor=C_BLACK)
    td_r = ParagraphStyle('TDR', fontSize=9.5, leading=13, fontName=FONT,
                          textColor=C_BLACK, alignment=TA_RIGHT)

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
    col_widths = [10 * mm, 62 * mm, 18 * mm, 22 * mm, 28 * mm, 30 * mm]
    items_table = Table(items_data, colWidths=col_widths)

    style_cmds = [
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 3.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ('BACKGROUND', (0, 0), (-1, 0), C_LIGHT_BG),
        ('LINEBELOW', (0, 0), (-1, 0), 0.75, C_GRAY),
        ('LINEBELOW', (0, num_items), (-1, num_items), 0.75, C_GRAY),
    ]
    for row in range(1, num_items + 1):
        style_cmds.append(('LINEBELOW', (0, row), (-1, row), 0.25, C_BORDER))

    items_table.setStyle(TableStyle(style_cmds))
    elements.append(items_table)
    elements.append(Spacer(1, 5 * mm))

    # Totals
    total_label = ParagraphStyle('TotL', fontSize=9.5, leading=13, fontName=FONT,
                                 textColor=C_MID, alignment=TA_RIGHT)
    total_val = ParagraphStyle('TotV', fontSize=9.5, leading=13, fontName=FONT_BOLD,
                               textColor=C_BLACK, alignment=TA_RIGHT)
    grand_label = ParagraphStyle('GL', fontSize=11, leading=15, fontName=FONT_BOLD,
                                 textColor=C_BLACK, alignment=TA_RIGHT)
    grand_val = ParagraphStyle('GV', fontSize=11, leading=15, fontName=FONT_BOLD,
                               textColor=C_BLACK, alignment=TA_RIGHT)

    totals_data = [
        [Paragraph("Summa bez PVN:", total_label),
         Paragraph(f"{data['subtotal']:.2f} EUR", total_val)],
        [Paragraph(f"PVN ({data['vat_rate']:.0f}%):", total_label),
         Paragraph(f"{data['vat_amount']:.2f} EUR", total_val)],
        [Paragraph("Kopā ar PVN:", grand_label),
         Paragraph(f"{data['total']:.2f} EUR", grand_val)],
    ]
    totals_table = Table(totals_data, colWidths=[128 * mm, 42 * mm])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEABOVE', (0, 2), (-1, 2), 0.75, C_DARK),
    ]))
    elements.append(totals_table)

    if doc["notes"]:
        elements.append(Spacer(1, 6 * mm))
        elements.append(Paragraph(f"<font name='{FONT_BOLD}'>Piezīmes:</font> {doc['notes']}", normal))

    elements.append(Spacer(1, 18 * mm))
    sig_style = ParagraphStyle('Sig', fontSize=9, leading=12, fontName=FONT, textColor=C_MID)
    sig_data = [[
        Paragraph(f"<font name='{FONT_BOLD}'>Izsniedza:</font>  ________________________", sig_style),
        Paragraph(f"<font name='{FONT_BOLD}'>Saņēma:</font>  ________________________", sig_style),
    ]]
    elements.append(Table(sig_data, colWidths=[85 * mm, 85 * mm]))

    pdf.build(elements)
    return filepath


# =============================================================================
# Template 2: Modern — Bold header band, structured, high contrast
# =============================================================================

def _generate_modern(doc_id):
    FONT, FONT_BOLD = _register_fonts()
    data = _get_doc_data(doc_id)
    doc = data["doc"]

    output_dir = get_output_dir()
    filename = f"{doc['doc_number']}.pdf"
    filepath = os.path.join(output_dir, filename)

    pdf = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm
    )

    styles = {
        "title": ParagraphStyle('Title', fontSize=18, fontName=FONT_BOLD,
                                textColor=C_WHITE, leading=22),
        "doc_info": ParagraphStyle('DocInfo', fontSize=10, fontName=FONT,
                                   textColor=colors.Color(0.85, 0.85, 0.85), leading=14),
        "section": ParagraphStyle('Section', fontSize=7.5, fontName=FONT_BOLD,
                                  textColor=C_MID, leading=10, spaceBefore=2 * mm),
        "normal": ParagraphStyle('N', fontSize=9, leading=13, fontName=FONT, textColor=C_BLACK),
        "bold": ParagraphStyle('B', fontSize=9, leading=13, fontName=FONT_BOLD, textColor=C_BLACK),
        "total_label": ParagraphStyle('TL', fontSize=9.5, leading=13,
                                      fontName=FONT, alignment=TA_RIGHT, textColor=C_MID),
        "total_value": ParagraphStyle('TV', fontSize=9.5, leading=13,
                                      fontName=FONT_BOLD, alignment=TA_RIGHT, textColor=C_BLACK),
        "grand_label": ParagraphStyle('GL', fontSize=12, leading=16,
                                      fontName=FONT_BOLD, alignment=TA_RIGHT, textColor=C_BLACK),
        "grand_value": ParagraphStyle('GV', fontSize=12, leading=16,
                                      fontName=FONT_BOLD, alignment=TA_RIGHT, textColor=C_BLACK),
    }

    elements = []

    # Dark header band (simulated with a table)
    logo_path = _get_logo_path(doc.get("user_id", 0))
    header_left = []
    if logo_path:
        logo_el = _make_logo_element(logo_path, max_width=45*mm, max_height=20*mm)
        if logo_el:
            header_left.append(logo_el)
            header_left.append(Spacer(1, 2 * mm))
    header_left.append(Paragraph(data["doc_type_label"], styles["title"]))

    header_right = Paragraph(
        f"Nr. {doc['doc_number']}<br/>Datums: {data['display_date']}",
        styles["doc_info"]
    )

    header_data = [[header_left, header_right]]
    header_table = Table(header_data, colWidths=[110 * mm, 64 * mm])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C_BLACK),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (0, -1), 14),
        ('RIGHTPADDING', (1, 0), (1, -1), 14),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 7 * mm))

    # Parties
    s_lines = [Paragraph("PIEGĀDĀTĀJS / PĀRDEVĒJS", styles["section"])] + \
              _party_lines(data['supplier'], FONT_BOLD, styles["normal"])
    b_lines = [Paragraph("PIRCĒJS", styles["section"])] + \
              _party_lines(data['buyer'], FONT_BOLD, styles["normal"])

    party_rows = []
    for i in range(max(len(s_lines), len(b_lines))):
        party_rows.append([
            s_lines[i] if i < len(s_lines) else "",
            b_lines[i] if i < len(b_lines) else "",
        ])

    party_table = Table(party_rows, colWidths=[87 * mm, 87 * mm])
    party_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('LEFTPADDING', (1, 0), (1, -1), 8 * mm),
    ]))
    elements.append(party_table)
    elements.append(Spacer(1, 6 * mm))

    # Items table
    th = ParagraphStyle('TH', fontSize=8, fontName=FONT_BOLD, textColor=C_WHITE, leading=11)
    td = ParagraphStyle('TD', fontSize=9, leading=13, fontName=FONT, textColor=C_BLACK)
    td_r = ParagraphStyle('TDR', fontSize=9, leading=13, fontName=FONT,
                          textColor=C_BLACK, alignment=TA_RIGHT)

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
        ('BACKGROUND', (0, 0), (-1, 0), C_DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), C_WHITE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, 0), 5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
    ]
    for row in range(1, num_items + 1):
        if row % 2 == 0:
            style_commands.append(('BACKGROUND', (0, row), (-1, row), C_LIGHT_BG))
        style_commands.append(('LINEBELOW', (0, row), (-1, row), 0.25, C_BORDER))

    items_table.setStyle(TableStyle(style_commands))
    elements.append(items_table)
    elements.append(Spacer(1, 5 * mm))

    # Totals
    totals_data = [
        [Paragraph("Summa bez PVN:", styles["total_label"]),
         Paragraph(f"{data['subtotal']:.2f} EUR", styles["total_value"])],
        [Paragraph(f"PVN ({data['vat_rate']:.0f}%):", styles["total_label"]),
         Paragraph(f"{data['vat_amount']:.2f} EUR", styles["total_value"])],
        [Paragraph("KOPĀ AR PVN:", styles["grand_label"]),
         Paragraph(f"{data['total']:.2f} EUR", styles["grand_value"])],
    ]
    totals_table = Table(totals_data, colWidths=[128 * mm, 40 * mm])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEABOVE', (0, 2), (-1, 2), 1, C_BLACK),
    ]))
    elements.append(totals_table)

    if doc["notes"]:
        elements.append(Spacer(1, 5 * mm))
        elements.append(Paragraph(
            f"<font name='{FONT_BOLD}'>Piezīmes:</font> {doc['notes']}",
            styles["normal"]
        ))

    elements.append(Spacer(1, 18 * mm))
    sig = ParagraphStyle('Sig', fontSize=8.5, leading=12, fontName=FONT, textColor=C_MID)
    sig_data = [[
        Paragraph(f"<font name='{FONT_BOLD}'>Izsniedza:</font>  ________________________", sig),
        Paragraph(f"<font name='{FONT_BOLD}'>Saņēma:</font>  ________________________", sig),
    ]]
    sig_table = Table(sig_data, colWidths=[85 * mm, 85 * mm])
    elements.append(sig_table)

    pdf.build(elements)
    return filepath


# =============================================================================
# Template 3: Minimal — Ultra-clean, lots of whitespace, refined typography
# =============================================================================

def _generate_minimal(doc_id):
    FONT, FONT_BOLD = _register_fonts()
    data = _get_doc_data(doc_id)
    doc = data["doc"]

    output_dir = get_output_dir()
    filename = f"{doc['doc_number']}.pdf"
    filepath = os.path.join(output_dir, filename)

    pdf = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=28 * mm, rightMargin=28 * mm,
        topMargin=25 * mm, bottomMargin=20 * mm
    )

    styles = {
        "title": ParagraphStyle('Title', fontSize=13, fontName=FONT_BOLD,
                                textColor=C_BLACK, leading=17, spaceAfter=1 * mm),
        "subtitle": ParagraphStyle('Sub', fontSize=9.5, fontName=FONT,
                                   textColor=C_SILVER, leading=13, spaceAfter=6 * mm),
        "label": ParagraphStyle('Label', fontSize=7, fontName=FONT_BOLD,
                                textColor=C_SILVER, leading=10,
                                spaceBefore=0, spaceAfter=0.5 * mm),
        "value": ParagraphStyle('Value', fontSize=9, fontName=FONT,
                                textColor=C_BLACK, leading=12.5),
        "normal": ParagraphStyle('N', fontSize=9, leading=12.5, fontName=FONT, textColor=C_BLACK),
    }

    elements = []

    # Logo
    logo_path = _get_logo_path(doc.get("user_id", 0))
    if logo_path:
        logo_el = _make_logo_element(logo_path, max_width=40*mm, max_height=20*mm)
        if logo_el:
            elements.append(logo_el)
            elements.append(Spacer(1, 5 * mm))

    # Header — title and number on a single clean line
    elements.append(Paragraph(data["doc_type_label"], styles["title"]))
    elements.append(Paragraph(
        f"Nr. {doc['doc_number']}  &nbsp;&nbsp;&middot;&nbsp;&nbsp;  {data['display_date']}",
        styles["subtitle"]
    ))

    # Very thin divider
    elements.append(HRFlowable(width="100%", thickness=0.25, color=C_BORDER, spaceAfter=6 * mm))

    # Parties
    def _min_party_block(title, info):
        lines = [Paragraph(title, styles["label"])]
        lines.append(Paragraph(f"<font name='{FONT_BOLD}'>{info['name']}</font>", styles["value"]))
        if info['reg']:
            lines.append(Paragraph(f"Reģ.Nr. {info['reg']}", styles["value"]))
        if info['vat']:
            lines.append(Paragraph(f"PVN {info['vat']}", styles["value"]))
        if info['addr']:
            lines.append(Paragraph(info['addr'], styles["value"]))
        if info['bank'] or info['account']:
            parts = []
            if info['bank']:
                parts.append(info['bank'])
            if info['account']:
                parts.append(info['account'])
            lines.append(Paragraph("  &middot;  ".join(parts), styles["value"]))
        return lines

    s_block = _min_party_block("PIEGĀDĀTĀJS", data["supplier"])
    b_block = _min_party_block("PIRCĒJS", data["buyer"])

    party_rows = []
    for i in range(max(len(s_block), len(b_block))):
        party_rows.append([
            s_block[i] if i < len(s_block) else "",
            b_block[i] if i < len(b_block) else "",
        ])

    party_table = Table(party_rows, colWidths=[77 * mm, 77 * mm])
    party_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 0.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),
        ('LEFTPADDING', (1, 0), (1, -1), 10 * mm),
    ]))
    elements.append(party_table)
    elements.append(Spacer(1, 8 * mm))

    # Items table — hairline borders, generous padding
    th = ParagraphStyle('TH', fontSize=7, fontName=FONT_BOLD, textColor=C_SILVER, leading=10)
    td = ParagraphStyle('TD', fontSize=9, leading=13, fontName=FONT, textColor=C_BLACK)
    td_r = ParagraphStyle('TDR', fontSize=9, leading=13, fontName=FONT,
                          textColor=C_BLACK, alignment=TA_RIGHT)

    items_data = [[
        Paragraph("#", th),
        Paragraph("PRECE / PAKALPOJUMS", th),
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
    col_widths = [8 * mm, 58 * mm, 16 * mm, 20 * mm, 25 * mm, 27 * mm]
    items_table = Table(items_data, colWidths=col_widths)

    style_cmds = [
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 4),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 4),
        ('TOPPADDING', (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, C_MID),
    ]
    for row in range(1, num_items + 1):
        style_cmds.append(('LINEBELOW', (0, row), (-1, row), 0.15, C_BORDER))
    # Stronger line after last item
    if num_items > 0:
        style_cmds.append(('LINEBELOW', (0, num_items), (-1, num_items), 0.5, C_MID))

    items_table.setStyle(TableStyle(style_cmds))
    elements.append(items_table)
    elements.append(Spacer(1, 5 * mm))

    # Totals
    tr = ParagraphStyle('TR', fontSize=9, leading=13, fontName=FONT,
                        textColor=C_SILVER, alignment=TA_RIGHT)
    tr_bold = ParagraphStyle('TRB', fontSize=10.5, leading=15, fontName=FONT_BOLD,
                             textColor=C_BLACK, alignment=TA_RIGHT)

    totals_data = [
        [Paragraph("Bez PVN", tr), Paragraph(f"{data['subtotal']:.2f} EUR", tr)],
        [Paragraph(f"PVN {data['vat_rate']:.0f}%", tr),
         Paragraph(f"{data['vat_amount']:.2f} EUR", tr)],
        [Paragraph("Kopā", tr_bold), Paragraph(f"{data['total']:.2f} EUR", tr_bold)],
    ]
    totals_table = Table(totals_data, colWidths=[118 * mm, 36 * mm])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
        ('LINEABOVE', (1, 2), (1, 2), 0.5, C_BLACK),
    ]))
    elements.append(totals_table)

    if doc["notes"]:
        elements.append(Spacer(1, 6 * mm))
        elements.append(HRFlowable(width="100%", thickness=0.15, color=C_BORDER, spaceAfter=2 * mm))
        elements.append(Paragraph(f"<font name='{FONT_BOLD}'>Piezīmes:</font> {doc['notes']}",
                                  styles["normal"]))

    elements.append(Spacer(1, 22 * mm))
    sig = ParagraphStyle('Sig', fontSize=8, leading=11, fontName=FONT, textColor=C_SILVER)
    sig_data = [[
        Paragraph("Izsniedza  ________________________", sig),
        Paragraph("Saņēma  ________________________", sig),
    ]]
    elements.append(Table(sig_data, colWidths=[77 * mm, 77 * mm]))

    pdf.build(elements)
    return filepath
