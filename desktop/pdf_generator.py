"""
PDF invoice generation for Veggie Invoice Manager.
Uses reportlab for PDF creation with Latvian character support.
"""

import os
import sys
import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import database as db


def _get_font_path(filename):
    """Find font file across different OS locations."""
    search_paths = [
        # Bundled with app (highest priority)
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts"),
        # Linux
        "/usr/share/fonts/truetype/dejavu",
        "/usr/local/share/fonts",
        # Windows
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts"),
    ]
    if getattr(sys, 'frozen', False):
        search_paths.insert(0, os.path.join(os.path.dirname(sys.executable), "fonts"))

    for path in search_paths:
        full = os.path.join(path, filename)
        if os.path.exists(full):
            return full
    return None


def _register_fonts():
    """Register fonts with Latvian character support."""
    from reportlab.pdfbase.pdfmetrics import registerFontFamily

    # Try DejaVu first (Linux, or bundled), then Arial (Windows fallback)
    font_options = [
        ("Arial", "arial.ttf", "Arial-Bold", "arialbd.ttf"),
        ("DejaVu", "DejaVuSans.ttf", "DejaVu-Bold", "DejaVuSans-Bold.ttf"),
    ]

    for font_name, font_file, bold_name, bold_file in font_options:
        try:
            pdfmetrics.getFont(font_name)
            return font_name, bold_name  # Already registered
        except KeyError:
            regular_path = _get_font_path(font_file)
            bold_path = _get_font_path(bold_file)
            if regular_path and bold_path:
                pdfmetrics.registerFont(TTFont(font_name, regular_path))
                pdfmetrics.registerFont(TTFont(bold_name, bold_path))
                registerFontFamily(font_name, normal=font_name, bold=bold_name)
                return font_name, bold_name

    # Last resort - Helvetica (built-in, no Latvian support)
    return "Helvetica", "Helvetica-Bold"


def get_output_dir():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, "dokumenti")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def generate_invoice_pdf(doc_id):
    FONT, FONT_BOLD = _register_fonts()

    doc, items = db.get_document(doc_id)
    if not doc:
        raise ValueError(f"Dokuments ar ID {doc_id} nav atrasts")

    client = db.get_client(doc["client_id"])
    settings = db.get_all_settings()

    output_dir = get_output_dir()
    filename = f"{doc['doc_number']}.pdf"
    filepath = os.path.join(output_dir, filename)

    pdf = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm
    )

    title_style = ParagraphStyle(
        'InvoiceTitle', fontSize=16, alignment=1, spaceAfter=6 * mm,
        fontName=FONT_BOLD, leading=20
    )
    doc_num_style = ParagraphStyle(
        'DocNum', fontSize=12, alignment=1, spaceAfter=8 * mm,
        fontName=FONT, leading=16
    )
    normal = ParagraphStyle('N', fontSize=10, leading=14, fontName=FONT)
    bold = ParagraphStyle('B', fontSize=10, leading=14, fontName=FONT_BOLD)

    elements = []

    # Title from settings
    if doc["doc_type"] == "buy":
        doc_type_label = settings.get("buy_doc_name", "PIRKUMA PAVADZĪME")
    else:
        doc_type_label = settings.get("sell_doc_name", "PĀRDOŠANAS PAVADZĪME")

    elements.append(Paragraph(doc_type_label, title_style))
    elements.append(Paragraph(f"Nr. {doc['doc_number']}", doc_num_style))
    # Format date as DD.MM.YYYY
    raw_date = doc['doc_date']
    try:
        from datetime import date as _date
        if isinstance(raw_date, str):
            d = _date.fromisoformat(raw_date)
        else:
            d = raw_date
        display_date = d.strftime("%d.%m.%Y")
    except Exception:
        display_date = raw_date

    elements.append(Paragraph(f"Datums: {display_date}", bold))
    elements.append(Spacer(1, 4 * mm))

    # Seller / Buyer
    if doc["doc_type"] == "buy":
        supplier_src, buyer_src = client, None
    else:
        supplier_src, buyer_src = None, client

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
            Paragraph(f"{label}: {supplier[key]}", normal),
            Paragraph(f"{label}: {buyer[key]}", normal),
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
    vat_rate = doc["vat_rate"]
    items_data = [[
        Paragraph(f"<font name='{FONT_BOLD}'>Nr.</font>", normal),
        Paragraph(f"<font name='{FONT_BOLD}'>Nosaukums</font>", normal),
        Paragraph(f"<font name='{FONT_BOLD}'>Mērv.</font>", normal),
        Paragraph(f"<font name='{FONT_BOLD}'>Daudzums</font>", normal),
        Paragraph(f"<font name='{FONT_BOLD}'>Cena</font>", normal),
        Paragraph(f"<font name='{FONT_BOLD}'>Summa</font>", normal),
    ]]

    subtotal = 0
    for i, item in enumerate(items, 1):
        line_total = item["quantity"] * item["price_per_unit"]
        subtotal += line_total
        items_data.append([
            Paragraph(str(i), normal),
            Paragraph(item["product_name"], normal),
            Paragraph(item["unit"], normal),
            Paragraph(f"{item['quantity']:.2f}", normal),
            Paragraph(f"{item['price_per_unit']:.2f}", normal),
            Paragraph(f"{line_total:.2f}", normal),
        ])

    vat_amount = subtotal * (vat_rate / 100)
    total = subtotal + vat_amount

    num_items = len(items)
    items_data.append(["", "", "", "",
                       Paragraph(f"<font name='{FONT_BOLD}'>Summa bez PVN:</font>", normal),
                       Paragraph(f"<font name='{FONT_BOLD}'>{subtotal:.2f}</font>", normal)])
    items_data.append(["", "", "", "",
                       Paragraph(f"<font name='{FONT_BOLD}'>PVN ({vat_rate:.0f}%):</font>", normal),
                       Paragraph(f"<font name='{FONT_BOLD}'>{vat_amount:.2f}</font>", normal)])
    items_data.append(["", "", "", "",
                       Paragraph(f"<font name='{FONT_BOLD}'>Kopā ar PVN:</font>", normal),
                       Paragraph(f"<font name='{FONT_BOLD}'>{total:.2f}</font>", normal)])

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
