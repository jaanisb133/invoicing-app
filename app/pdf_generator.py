"""
PDF documents for V-Rēķini: invoices, offers and purchase documents.

Three templates share one set of parts (header, parties, lines, totals,
payment details, notes, sign-off, page footer) and differ in character:

  classic  letterhead: a serif title over a double rule in the accent colour
  modern   the amount due leads, in an accent panel under the header
  minimal  hairlines, a strict grid and a lot of white space

The editor and document previews (static/js/paper.js) draw the same layouts
in HTML at scale, so a change here needs the same change there.
"""

from app import fmt
import os
import datetime
from xml.sax.saxutils import escape as _xml_escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Table, TableStyle, Paragraph, Spacer, Image, Flowable, KeepTogether
)
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT
from reportlab.pdfgen import canvas as rl_canvas

from app import database as db

# Available templates
TEMPLATES = {
    "classic": "Klasiskā",
    "modern": "Modernā",
    "minimal": "Minimālā",
}

PAGE_W, PAGE_H = A4

# Ink and greys are the same in every template; colour comes from the accent only
INK = colors.HexColor("#111418")
BODY = colors.HexColor("#2b2f36")
MUTED = colors.HexColor("#686d76")
FAINT = colors.HexColor("#9a9ea6")
RULE = colors.HexColor("#e1e3e7")
PANEL = colors.HexColor("#f4f5f7")
C_WHITE = colors.white
DEFAULT_ACCENT = "#09090b"


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
    """Register a regular + bold pair with Latvian characters (used by pdf_branded too).
    Prefers DM Sans, then Liberation Sans, DejaVu Sans, Arial, Helvetica."""
    from reportlab.pdfbase.pdfmetrics import registerFontFamily

    font_options = [
        ("DMSans", "DMSans-Regular.ttf", "DMSans-Bold", "DMSans-Bold.ttf"),
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


_FACE_FILES = {
    "sans": "DMSans-Regular.ttf",
    "sans_md": "DMSans-Medium.ttf",
    "sans_sb": "DMSans-SemiBold.ttf",
    "sans_b": "DMSans-Bold.ttf",
    "sans_i": "DMSans-Italic.ttf",
    "serif": "SourceSerif4-Regular.ttf",
    "serif_sb": "SourceSerif4-SemiBold.ttf",
    "serif_i": "SourceSerif4-Italic.ttf",
}
_FACES = {}


def _faces():
    """Every face the templates use; a missing file falls back to the base pair."""
    if _FACES:
        return _FACES
    base, bold = _register_fonts()
    for key, filename in _FACE_FILES.items():
        name = "VR-" + key
        try:
            pdfmetrics.getFont(name)
            _FACES[key] = name
            continue
        except KeyError:
            pass
        path = _get_font_path(filename)
        if path:
            pdfmetrics.registerFont(TTFont(name, path))
            _FACES[key] = name
        else:
            _FACES[key] = bold if key in ("sans_sb", "sans_b", "serif_sb") else base
    return _FACES


def get_output_dir():
    app_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(os.path.dirname(app_dir), "data", "dokumenti")
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def _safe_filename(doc_number):
    """Sanitize doc_number for use as a filename (replace / with _)."""
    return doc_number.replace("/", "_")


def _get_logo_path(user_id):
    app_dir = os.path.dirname(os.path.abspath(__file__))
    logo_dir = os.path.join(os.path.dirname(app_dir), "data", "logos")
    filename = db.get_user_setting(user_id, "logo_filename")
    if filename:
        path = os.path.join(logo_dir, filename)
        if os.path.exists(path):
            return path
    return None


def _logo(path, max_w, max_h, settings):
    """The account's logo scaled into a box; logo_width (50–150 %) scales the box."""
    if not path:
        return None
    try:
        pct = max(40, min(160, int(settings.get("logo_width", "100") or 100)))
    except (TypeError, ValueError):
        pct = 100
    max_w, max_h = max_w * pct / 100, max_h * pct / 100
    try:
        img = Image(path)
        w, h = img.imageWidth, img.imageHeight
        if w <= 0 or h <= 0:
            return None
        ratio = min(max_w / w, max_h / h)
        img.drawWidth, img.drawHeight = w * ratio, h * ratio
        img.hAlign = "LEFT"
        return img
    except Exception:
        return None


def _quotes(text):
    """SIA "Bērzu Darbnīca" -> SIA „Bērzu Darbnīca”: Latvian quotes in print. Names
    are stored as typed (usually straight quotes); only the document changes them."""
    out, opening = [], True
    for ch in str(text or ""):
        if ch == '"':
            out.append("\u201e" if opening else "\u201d")
            opening = not opening
        else:
            out.append(ch)
    return "".join(out)


def _x(text):
    """User text for a Paragraph: escaped, with its line breaks kept."""
    return _xml_escape(str(text or "").strip()).replace("\r\n", "\n").replace("\n", "<br/>")


def _xq(text):
    """A name or address for a Paragraph, in Latvian quotes. Not for line items:
    27" there means inches."""
    return _x(_quotes(text))


def _iban(account):
    """LV80BANK0000435195001 -> LV80 BANK 0000 4351 9500 1 (an IBAN is read in fours)."""
    raw = (account or "").replace(" ", "")
    if len(raw) > 12 and raw[:2].isalpha() and raw[2:4].isdigit():
        return " ".join(raw[i:i + 4] for i in range(0, len(raw), 4))
    return account or ""


def _hex_to_color(hex_str):
    """Convert a hex color string like '#1f2937' to a ReportLab Color."""
    h = (hex_str or "").lstrip('#')
    if len(h) != 6:
        return INK
    try:
        return colors.Color(int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255)
    except ValueError:
        return INK


def _is_light(c):
    return 0.2126 * c.red + 0.7152 * c.green + 0.0722 * c.blue > 0.62


def _tint(c, amount):
    """The accent mixed into white: amount 0.06 is a 6 % wash."""
    return colors.Color(1 - (1 - c.red) * amount, 1 - (1 - c.green) * amount, 1 - (1 - c.blue) * amount)


def _date(raw):
    if not raw:
        return ""
    try:
        d = datetime.date.fromisoformat(raw) if isinstance(raw, str) else raw
        return d.strftime("%d.%m.%Y")
    except (TypeError, ValueError):
        return str(raw)


def _get_doc_data(doc_id):
    """Everything a document's PDF needs, in one dict (pdf_branded reads it too)."""
    doc, items = db.get_document(doc_id)
    if not doc:
        raise ValueError(f"Dokuments ar ID {doc_id} nav atrasts")

    client = db.get_client(doc["client_id"])
    user_id = doc.get("user_id", 0)
    settings = db.get_all_user_settings(user_id) if user_id else db.get_all_settings()

    if doc["doc_type"] == "buy":
        doc_type_label = settings.get("buy_doc_name", "Rēķins")
    elif doc["doc_type"] == "offer":
        doc_type_label = settings.get("offer_doc_name", "Piedāvājums")
    else:
        doc_type_label = settings.get("sell_doc_name", "Rēķins")
    doc_type_label = (doc_type_label or "Rēķins").strip()

    entity_type = settings.get("entity_type", "business")

    def party_info(source_client, from_settings=False):
        if from_settings:
            return {
                "name": (settings.get("company_name", "") or "").strip(),
                "reg": (settings.get("reg_number", "") or "").strip(),
                "vat": (settings.get("vat_number", "") or "").strip(),
                "addr": (settings.get("legal_address", "") or "").strip(),
                "bank": (settings.get("bank_name", "") or "").strip(),
                "account": (settings.get("bank_account", "") or "").strip(),
                "is_own": True,
                "is_person": entity_type == "individual",
            }
        c = source_client or {}
        return {
            "name": (c.get("name") or "").strip(),
            "reg": (c.get("reg_number") or "").strip(),
            "vat": (c.get("vat_number") or "").strip(),
            "addr": (c.get("legal_address") or "").strip(),
            "bank": (c.get("bank_name") or "").strip(),
            "account": (c.get("bank_account") or "").strip(),
            "is_own": False,
            "is_person": (c.get("client_type") or "business") == "individual",
        }

    if doc["doc_type"] == "buy":
        supplier = party_info(client)
        buyer = party_info(None, from_settings=True)
    else:
        supplier = party_info(None, from_settings=True)
        buyer = party_info(client)

    subtotal = sum(
        0 if item.get("included_in_price") else item["quantity"] * item["price_per_unit"]
        for item in items
    )
    # Under reverse charge the supplier charges no VAT, whatever rate is stored
    vat_rate = 0.0 if doc.get("reverse_charge") else doc["vat_rate"]
    vat_amount = subtotal * (vat_rate / 100)
    total = subtotal + vat_amount

    display_due_date = _date(doc.get("payment_due_date")) if doc.get("doc_type") != "offer" else ""

    return {
        "doc": doc,
        "items": items,
        "client": client,
        "settings": settings,
        "display_date": _date(doc["doc_date"]),
        "display_due_date": display_due_date,
        "doc_type_label": doc_type_label,
        "supplier": supplier,
        "buyer": buyer,
        "subtotal": subtotal,
        "vat_rate": vat_rate,
        "vat_amount": vat_amount,
        "total": total,
        "is_vat_payer": settings.get("is_vat_payer", "1") == "1",
        "entity_type": entity_type,
        "reverse_charge": bool(doc.get("reverse_charge", 0)),
    }


FREE_PLAN_FOOTER = "Sagatavots ar V-Rēķini · v-rekini.lv"


def _free_plan(data):
    owner = db.get_user(data["doc"]["user_id"])
    return bool(owner) and owner.get("tier", "free") == "free"


def _plan_footer(data, font):
    """Page callback: invoices made on the free plan carry one small line at the
    foot of the page. Paid plans and trials print nothing. (pdf_branded uses it.)"""
    if not _free_plan(data):
        return lambda canvas, doc: None

    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont(font, 7)
        canvas.setFillColor(FAINT)
        canvas.drawCentredString(PAGE_W / 2, 7 * mm, FREE_PLAN_FOOTER)
        canvas.restoreState()
    return draw


def generate_invoice_pdf(doc_id, template="minimal"):
    if template not in TEMPLATES:
        template = "minimal"
    return _build(doc_id, template)


# =============================================================================
# Templates: geometry and type, per character
# =============================================================================

THEMES = {
    "classic": {
        "margin_x": 20 * mm, "margin_top": 18 * mm, "margin_bottom": 26 * mm,
        "title_face": "serif", "title_size": 30, "name_face": "serif_sb", "name_size": 10.5,
        "label_upper": True, "amount_face": "serif_sb", "amount_size": 17,
        "table_head_fill": False, "table_head_rule": INK,
    },
    "modern": {
        "margin_x": 18 * mm, "margin_top": 16 * mm, "margin_bottom": 26 * mm,
        "title_face": "sans_sb", "title_size": 22, "name_face": "sans_sb", "name_size": 9.5,
        "label_upper": False, "amount_face": "sans_sb", "amount_size": 14,
        "table_head_fill": True, "table_head_rule": None,
    },
    "minimal": {
        "margin_x": 22 * mm, "margin_top": 22 * mm, "margin_bottom": 28 * mm,
        "title_face": "sans", "title_size": 24, "name_face": "sans_md", "name_size": 9.5,
        "label_upper": True, "amount_face": "sans", "amount_size": 18,
        "table_head_fill": False, "table_head_rule": INK,
    },
}


class _Label(Flowable):
    """A small letter-spaced label. Paragraph cannot track type, the canvas can."""

    def __init__(self, text, face, size=6.8, color=MUTED, upper=True, align="left", tracking=None):
        super().__init__()
        self.text = text.upper() if upper else text
        self.face, self.size, self.color, self.align = face, size, color, align
        self.tracking = (0.07 * size if upper else 0) if tracking is None else tracking
        self.text_w = pdfmetrics.stringWidth(self.text, face, size) + self.tracking * max(len(self.text) - 1, 0)

    def wrap(self, aw, ah):
        self.avail = aw
        return (aw, self.size * 1.5)

    def draw(self):
        x = self.avail - self.text_w if self.align == "right" else 0
        self.canv.setFillColor(self.color)
        self.canv.setFont(self.face, self.size)
        self.canv.drawString(x, self.size * 0.42, self.text, charSpace=self.tracking)


class _Panel(Flowable):
    """The modern template's summary: the amount large, then the dates, on one
    shared baseline in a rounded block of the accent colour."""

    def __init__(self, cells, accent, faces, height=24 * mm):
        super().__init__()
        self.cells, self.accent, self.F, self.h = cells, accent, faces, height

    def wrap(self, aw, ah):
        self.w = aw
        return (aw, self.h)

    def draw(self):
        c, F = self.canv, self.F
        ink = INK if _is_light(self.accent) else C_WHITE
        soft = colors.Color(ink.red, ink.green, ink.blue, alpha=0.62)
        c.setFillColor(self.accent)
        c.roundRect(0, 0, self.w, self.h, 5, stroke=0, fill=1)
        pad = 6 * mm
        first_w = self.w * 0.46
        rest = (self.w - first_w) / max(1, len(self.cells) - 1)
        base = 6.2 * mm
        for i, (label, value) in enumerate(self.cells):
            x = pad if i == 0 else first_w + rest * (i - 1)
            c.setFillColor(soft)
            c.setFont(F["sans_md"], 7.6)
            c.drawString(x, self.h - 7.4 * mm, label)
            c.setFillColor(ink)
            if i == 0:
                c.setFont(F["sans_sb"], 23)
            else:
                c.setFont(F["sans_md"], 11.5)
            c.drawString(x, base, value)


class _Rule(Flowable):
    """A horizontal rule, or the classic double rule (thick over thin)."""

    def __init__(self, color, weight=0.5, double=False, space_after=0):
        super().__init__()
        self.color, self.weight, self.double, self.space_after = color, weight, double, space_after

    def wrap(self, aw, ah):
        self.avail = aw
        return (aw, (3.2 if self.double else self.weight) + self.space_after)

    def draw(self):
        c = self.canv
        c.setStrokeColor(self.color)
        top = (3.2 if self.double else self.weight) + self.space_after
        if self.double:
            c.setLineWidth(1.4)
            c.line(0, top - 0.7, self.avail, top - 0.7)
            c.setLineWidth(0.45)
            c.line(0, top - 2.95, self.avail, top - 2.95)
        else:
            c.setLineWidth(self.weight)
            c.line(0, top - self.weight / 2, self.avail, top - self.weight / 2)


def _numbered_canvas(draw_chrome):
    """A canvas that knows the page count, so each page can say "1 / 2"."""

    class NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            count = len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                draw_chrome(self, self._pageNumber, count)
                super().showPage()
            super().save()

    return NumberedCanvas


# =============================================================================
# Build
# =============================================================================

def _build(doc_id, template):
    F = _faces()
    T = THEMES[template]
    data = _get_doc_data(doc_id)
    doc = data["doc"]
    s = data["settings"]
    accent = _hex_to_color(s.get("accent_color") or DEFAULT_ACCENT)
    width = PAGE_W - 2 * T["margin_x"]

    filepath = os.path.join(get_output_dir(), f"{_safe_filename(doc['doc_number'])}.pdf")
    pdf = BaseDocTemplate(
        filepath, pagesize=A4,
        leftMargin=T["margin_x"], rightMargin=T["margin_x"],
        topMargin=T["margin_top"], bottomMargin=T["margin_bottom"],
        title=f"{data['doc_type_label']} Nr. {doc['doc_number']}",
        author=_quotes(data["supplier"]["name"] if doc["doc_type"] != "buy" else data["buyer"]["name"]),
        creator="V-Rēķini",
    )
    # No frame padding: every part is measured against the margins themselves
    frame = Frame(T["margin_x"], T["margin_bottom"], width, PAGE_H - T["margin_top"] - T["margin_bottom"],
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="body")
    pdf.addPageTemplates([PageTemplate(id="page", frames=[frame])])

    ctx = {
        "F": F, "T": T, "data": data, "doc": doc, "s": s, "accent": accent, "width": width,
        "template": template, "kind": doc["doc_type"],
        "logo": _logo(_get_logo_path(doc.get("user_id", 0)),
                      46 * mm if template != "minimal" else 38 * mm,
                      17 * mm if template != "minimal" else 13 * mm, s),
    }
    st = _styles(ctx)
    ctx["st"] = st

    story = []
    story += {"classic": _head_classic, "modern": _head_modern, "minimal": _head_minimal}[template](ctx)
    story += _parties(ctx)
    story.append(_lines(ctx))
    story.append(KeepTogether(_summary(ctx)))
    story += _notes(ctx)
    story.append(KeepTogether(_sign_off(ctx)))

    pdf.build(story, canvasmaker=_numbered_canvas(_chrome(ctx)))
    return filepath


def _styles(ctx):
    F, T = ctx["F"], ctx["T"]
    base = 8.8 if ctx["template"] != "minimal" else 8.6

    def ps(name, **kw):
        kw.setdefault("fontName", F["sans"])
        kw.setdefault("fontSize", base)
        kw.setdefault("leading", kw["fontSize"] * 1.45)
        kw.setdefault("textColor", BODY)
        return ParagraphStyle(name, **kw)

    return {
        "body": ps("body"),
        "muted": ps("muted", textColor=MUTED),
        "name": ps("name", fontName=F[T["name_face"]], fontSize=T["name_size"], textColor=INK,
                   leading=T["name_size"] * 1.35, spaceAfter=1.5),
        "cell": ps("cell", fontSize=8.6, leading=12.2, textColor=INK),
        "cell_r": ps("cell_r", fontSize=8.6, leading=12.2, textColor=INK, alignment=TA_RIGHT),
        "cell_m": ps("cell_m", fontSize=8.6, leading=12.2, textColor=MUTED),
        "cell_mr": ps("cell_mr", fontSize=8.6, leading=12.2, textColor=MUTED, alignment=TA_RIGHT),
        "head": ps("head", fontName=F["sans_md"], fontSize=7.2, leading=9.5, textColor=MUTED),
        "head_r": ps("head_r", fontName=F["sans_md"], fontSize=7.2, leading=9.5, textColor=MUTED, alignment=TA_RIGHT),
        "kv_k": ps("kv_k", fontSize=8.2, leading=12, textColor=MUTED),
        "kv_v": ps("kv_v", fontSize=8.2, leading=12, textColor=INK),
        "kv_vr": ps("kv_vr", fontSize=8.6, leading=12.4, textColor=INK, alignment=TA_RIGHT),
        "kv_kr": ps("kv_kr", fontSize=8.6, leading=12.4, textColor=MUTED, alignment=TA_RIGHT),
        "amount_k": ps("amount_k", fontName=F["sans_md"], fontSize=9.5, leading=13, textColor=INK),
        "amount_v": ps("amount_v", fontName=F[T["amount_face"]], fontSize=T["amount_size"],
                       leading=T["amount_size"] * 1.2, textColor=INK, alignment=TA_RIGHT),
        "note": ps("note", fontSize=8.4, leading=12.4, textColor=BODY),
        "small": ps("small", fontSize=7.4, leading=10.4, textColor=MUTED),
    }


def _label(ctx, text, align="left", color=MUTED):
    T, F = ctx["T"], ctx["F"]
    if T["label_upper"]:
        return _Label(text, F["sans_sb"], 6.4, color, upper=True, align=align)
    return _Label(text, F["sans_md"], 7.6, color, upper=False, align=align)


def _identity(ctx, max_w):
    """The supplier's logo, or its name set as a wordmark."""
    if ctx["logo"] is not None and ctx["kind"] != "buy":
        return ctx["logo"]
    F = ctx["F"]
    name = ctx["data"]["supplier"]["name"] or " "
    face = F["serif_sb"] if ctx["template"] == "classic" else F["sans_sb"]
    size = 13 if ctx["template"] != "minimal" else 10.5
    return Paragraph(_xq(name), ParagraphStyle("wordmark", fontName=face, fontSize=size,
                                              leading=size * 1.2, textColor=INK))


def _meta_rows(ctx):
    """Number and dates as (label, value) rows."""
    data, doc = ctx["data"], ctx["doc"]
    rows = [("Numurs", doc["doc_number"]), ("Datums", data["display_date"])]
    if data["display_due_date"]:
        rows.append(("Apmaksāt līdz", data["display_due_date"]))
    return rows


def _kv_table(ctx, rows, key_w, align_right=False, size=None):
    st = ctx["st"]
    k, v = (st["kv_kr"], st["kv_vr"]) if align_right else (st["kv_k"], st["kv_v"])
    t = Table([[Paragraph(_x(a), k), Paragraph(_x(b), v)] for a, b in rows],
              colWidths=[key_w, None], hAlign="RIGHT" if align_right else "LEFT")
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


# ---------------------------------------------------------------- headers

def _head_classic(ctx):
    data, st, F, width = ctx["data"], ctx["st"], ctx["F"], ctx["width"]
    title = Paragraph(_x(data["doc_type_label"]), ParagraphStyle(
        "title", fontName=F["serif"], fontSize=30, leading=32, textColor=INK))
    meta = _kv_table(ctx, _meta_rows(ctx), 26 * mm, align_right=True)
    meta._argW = [26 * mm, 30 * mm]
    top = Table([[_identity(ctx, 90 * mm), ""]], colWidths=[width * 0.6, width * 0.4])
    row = Table([[title, meta]], colWidths=[width - 62 * mm, 62 * mm])
    for t in (top, row):
        t.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ]))
    return [top, Spacer(1, 13 * mm), row, Spacer(1, 4.5 * mm),
            _Rule(ctx["accent"], double=True), Spacer(1, 8 * mm)]


def _head_modern(ctx):
    data, F, width, accent, doc = ctx["data"], ctx["F"], ctx["width"], ctx["accent"], ctx["doc"]
    title = Paragraph(
        f"{_x(data['doc_type_label'])}<br/><font name='{F['sans']}' size='9.5' color='#686d76'>"
        f"Nr. {_x(doc['doc_number'])}</font>",
        ParagraphStyle("title", fontName=F["sans_sb"], fontSize=21, leading=24, textColor=INK, alignment=TA_RIGHT))
    top = Table([[_identity(ctx, 90 * mm), title]], colWidths=[width * 0.55, width * 0.45])
    top.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    # The panel: what is owed and by when, before anything else
    payable = ctx["kind"] == "sell"
    cells = [("Apmaksai" if payable else "Kopā", fmt.eur(data["total"]))]
    if data["display_due_date"]:
        cells.append(("Apmaksāt līdz", data["display_due_date"]))
    cells.append(("Datums", data["display_date"]))
    panel = _Panel(cells, accent, F)
    return [top, Spacer(1, 9 * mm), panel, Spacer(1, 9 * mm)]


def _head_minimal(ctx):
    data, F, width, doc = ctx["data"], ctx["F"], ctx["width"], ctx["doc"]
    top = Table([[_identity(ctx, 80 * mm), ""]], colWidths=[width * 0.6, width * 0.4])
    top.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
    ]))
    title = Paragraph(
        f"{_x(data['doc_type_label'])} <font color='#9a9ea6'>{_x(doc['doc_number'])}</font>",
        ParagraphStyle("title", fontName=F["sans"], fontSize=24, leading=28, textColor=INK))
    marker = _Rule(ctx["accent"], weight=2.2)
    marker_t = Table([[marker]], colWidths=[9 * mm], hAlign="LEFT")
    marker_t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                  ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return [top, Spacer(1, 18 * mm), marker_t, Spacer(1, 4 * mm), title, Spacer(1, 10 * mm)]


# ---------------------------------------------------------------- parties

def _party(ctx, title, info):
    st, data = ctx["st"], ctx["data"]
    out = [_label(ctx, title), Spacer(1, 2.2), Paragraph(_xq(info["name"] or "—"), st["name"])]
    lines = []
    if info["reg"]:
        lines.append(("P. k. " if info.get("is_person") else "Reģ. Nr. ") + info["reg"])
    if info["vat"] and data["is_vat_payer"]:
        lines.append("PVN Nr. " + info["vat"])
    if info["addr"]:
        lines.append(info["addr"])
    if lines:
        out.append(Paragraph("<br/>".join(_xq(l) for l in lines), st["muted"]))
    return out


def _parties(ctx):
    data, width, template = ctx["data"], ctx["width"], ctx["template"]
    left = _party(ctx, "Piegādātājs", data["supplier"])
    right = _party(ctx, "Saņēmējs", data["buyer"])
    if template == "minimal":
        # Three columns: the two parties, then the dates
        third = [_label(ctx, "Datumi"), Spacer(1, 2.2), _kv_table(ctx, _meta_rows(ctx)[1:] or [("", "")], 23 * mm)]
        t = Table([[left, right, third]], colWidths=[width * 0.36, width * 0.36, width * 0.28])
    else:
        gap = 8 * mm
        t = Table([[left, right]], colWidths=[(width - gap) / 2 + gap, (width - gap) / 2])
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 6 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return [t, Spacer(1, 10 * mm if template != "modern" else 9 * mm)]


# ---------------------------------------------------------------- lines

def _lines(ctx):
    st, width, T, accent, data = ctx["st"], ctx["width"], ctx["T"], ctx["accent"], ctx["data"]
    w_nr = 9.5 * mm if T["table_head_fill"] else 7.5 * mm
    w_qty, w_unit, w_price, w_sum = 17 * mm, 14 * mm, 23 * mm, 26 * mm
    w_name = width - (w_nr + w_qty + w_unit + w_price + w_sum)
    head = [Paragraph("Nr.", st["head"]), Paragraph("Apraksts", st["head"]), Paragraph("Daudz.", st["head_r"]),
            Paragraph("Mērv.", st["head"]), Paragraph("Cena", st["head_r"]), Paragraph("Summa", st["head_r"])]
    rows = [head]
    spans = []
    for i, item in enumerate(data["items"], 1):
        included = bool(item.get("included_in_price"))
        row = [Paragraph(str(i), st["cell_m"]), Paragraph(_x(item["product_name"]), st["cell"]),
               Paragraph(fmt.qty(item["quantity"]), st["cell_r"]), Paragraph(_x(item["unit"]), st["cell_m"])]
        if included:
            row += [Paragraph("iekļauts cenā", st["cell_mr"]), ""]
            spans.append(("SPAN", (4, i), (5, i)))
        else:
            row += [Paragraph(fmt.num(item["price_per_unit"]), st["cell_r"]),
                    Paragraph(fmt.num(item["quantity"] * item["price_per_unit"]), st["cell_r"])]
        rows.append(row)
    if len(rows) == 1:
        rows.append(["", Paragraph("Nav rindu", st["cell_m"]), "", "", "", ""])

    n = len(rows) - 1
    cmds = [
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (3, 0), (3, -1), 3 * mm),
        ("TOPPADDING", (0, 1), (-1, -1), 2.9 * mm), ("BOTTOMPADDING", (0, 1), (-1, -1), 2.7 * mm),
        ("TOPPADDING", (0, 0), (-1, 0), 2.4 * mm), ("BOTTOMPADDING", (0, 0), (-1, 0), 2.2 * mm),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 1), (-1, n - 1), 0.4, RULE),
        ("LINEBELOW", (0, n), (-1, n), 0.6, T["table_head_rule"] or RULE),
    ] + spans
    if T["table_head_fill"]:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), _tint(accent, 0.07) if not _is_light(accent) else _tint(accent, 0.35)),
                 ("LEFTPADDING", (0, 0), (0, -1), 2.5 * mm), ("RIGHTPADDING", (-1, 0), (-1, -1), 2.5 * mm),
                 ("ROUNDEDCORNERS", [3, 3, 0, 0])]
    else:
        cmds += [("LINEABOVE", (0, 0), (-1, 0), 0.6, T["table_head_rule"]),
                 ("LINEBELOW", (0, 0), (-1, 0), 0.4, T["table_head_rule"])]
    t = Table(rows, colWidths=[w_nr, w_name, w_qty, w_unit, w_price, w_sum], repeatRows=1)
    t.setStyle(TableStyle(cmds))
    return t


# ---------------------------------------------------------------- totals + payment

def _totals(ctx, box_w):
    """Net and VAT as quiet rows, then the amount on its own line under a rule."""
    st, data = ctx["st"], ctx["data"]
    plain = [
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
    ]
    out = []
    if data["is_vat_payer"]:
        if data["reverse_charge"]:
            rows = [("Summa bez PVN", fmt.eur(data["subtotal"])), ("Nodokļa apgrieztā maksāšana", "—")]
        else:
            rows = [("Summa bez PVN", fmt.eur(data["subtotal"])),
                    (f"PVN {fmt.qty(data['vat_rate'])}\u00a0%", fmt.eur(data["vat_amount"]))]
        t = Table([[Paragraph(_x(k), st["kv_k"]), Paragraph(v, st["kv_vr"])] for k, v in rows],
                  colWidths=[box_w * 0.64, box_w * 0.36])
        t.setStyle(TableStyle(plain))
        out += [t, Spacer(1, 2.2 * mm), _Rule(INK, weight=0.9 if ctx["template"] == "classic" else 0.6),
                Spacer(1, 2.6 * mm)]
    label = "Apmaksai" if ctx["kind"] == "sell" else "Kopā"
    t = Table([[Paragraph(label, st["amount_k"]), Paragraph(fmt.eur(data["total"]), st["amount_v"])]],
              colWidths=[box_w * 0.3, box_w * 0.7])
    t.setStyle(TableStyle(plain + [("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    out.append(t)
    return out


def _payment(ctx):
    """Where to pay: only on sales invoices that have an account to pay into."""
    data, doc = ctx["data"], ctx["doc"]
    sup = data["supplier"]
    if ctx["kind"] != "sell" or not sup["account"]:
        return None
    rows = []
    if sup["bank"]:
        rows.append(("Banka", _quotes(sup["bank"])))
    rows.append(("Konts", _iban(sup["account"])))
    rows.append(("Maksājuma mērķis", f"{data['doc_type_label']} Nr. {doc['doc_number']}"))
    if data["display_due_date"] and ctx["template"] != "modern":
        rows.append(("Apmaksāt līdz", data["display_due_date"]))
    return [_label(ctx, "Maksājuma informācija"), Spacer(1, 2.4), _kv_table(ctx, rows, 31 * mm)]


def _summary(ctx):
    width, template = ctx["width"], ctx["template"]
    box_w = 72 * mm if template != "minimal" else 66 * mm
    pay = _payment(ctx)
    totals = _totals(ctx, box_w)
    left_w = width - box_w
    if pay and template == "modern":
        inner = Table([[pay]], colWidths=[left_w - 10 * mm])
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), PANEL), ("ROUNDEDCORNERS", [4, 4, 4, 4]),
            ("LEFTPADDING", (0, 0), (-1, -1), 4.5 * mm), ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 3.6 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.6 * mm),
        ]))
        pay = [inner]
    t = Table([[pay or "", totals]], colWidths=[left_w, box_w])
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return [Spacer(1, 6 * mm), t]


def _notes(ctx):
    notes = (ctx["doc"].get("notes") or "").strip()
    if not notes:
        return []
    return [Spacer(1, 9 * mm), _label(ctx, "Piezīmes"), Spacer(1, 2.2),
            Paragraph(_x(notes), ctx["st"]["note"])]


def _sign_off(ctx):
    st, s, width = ctx["st"], ctx["s"], ctx["width"]
    if s.get("electronic_doc") == "1":
        return [Spacer(1, 12 * mm),
                Paragraph("Dokuments ir sagatavots elektroniski un ir derīgs bez paraksta.", st["small"])]
    gap = 14 * mm
    col = (width - gap) / 2
    t = Table([["", "", ""], [Paragraph("Izsniedza", st["small"]), "", Paragraph("Saņēma", st["small"])]],
              colWidths=[col, gap, col], rowHeights=[16 * mm, None])
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 1), (-1, 1), 1.6 * mm), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LINEBELOW", (0, 0), (0, 0), 0.5, FAINT), ("LINEBELOW", (2, 0), (2, 0), 0.5, FAINT),
    ]))
    return [Spacer(1, 8 * mm), t]


# ---------------------------------------------------------------- page chrome

def _chrome(ctx):
    """Footer on every page (supplier contacts, page x / n), a running header from
    page 2, and the free-plan line."""
    F, T, data, s, doc = ctx["F"], ctx["T"], ctx["data"], ctx["s"], ctx["doc"]
    mx = T["margin_x"]
    free = _free_plan(data)
    own = data["supplier"] if ctx["kind"] != "buy" else data["buyer"]
    contacts = [c for c in (s.get("company_email", ""), s.get("company_phone", ""), s.get("company_website", "")) if c and c.strip()]
    left_top = _quotes(own["name"])
    left_bottom = "  ·  ".join(c.strip() for c in contacts) if contacts else own["addr"]
    title = f"{data['doc_type_label']} Nr. {doc['doc_number']}"
    left_bottom = _quotes(left_bottom)

    def draw(c, page, count):
        c.saveState()
        y = T["margin_bottom"] - 12 * mm
        c.setStrokeColor(RULE)
        c.setLineWidth(0.4)
        c.line(mx, y + 8.6 * mm, PAGE_W - mx, y + 8.6 * mm)
        c.setFillColor(MUTED)
        c.setFont(F["sans_md"], 7)
        c.drawString(mx, y + 4.4 * mm, left_top[:90])
        c.setFont(F["sans"], 7)
        if left_bottom:
            c.drawString(mx, y + 1 * mm, left_bottom[:120])
        c.drawRightString(PAGE_W - mx, y + 4.4 * mm, title)
        c.drawRightString(PAGE_W - mx, y + 1 * mm, f"{page} / {count}")
        if page > 1:
            c.setFont(F["sans_md"], 7.4)
            c.drawString(mx, PAGE_H - 11 * mm, left_top[:90])
            c.setFont(F["sans"], 7.4)
            c.drawRightString(PAGE_W - mx, PAGE_H - 11 * mm, title)
        if free:
            c.setFont(F["sans"], 6.6)
            c.setFillColor(FAINT)
            c.drawCentredString(PAGE_W / 2, 6 * mm, FREE_PLAN_FOOTER)
        c.restoreState()

    return draw
