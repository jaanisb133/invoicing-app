"""
Branded offer ("tāme") PDF for accounts with the custom design enabled.

One fixed premium layout — dark diagonal header, gold accents, spec /
benefit boxes, product table, totals band, photo strip. All *text* comes
from the document's offer_meta (copied from an offer preset at save time),
so the client duplicates presets and edits content while the layout,
colors and typography stay locked.

Drawn directly on the canvas: the design is too bespoke for platypus
flowables, and manual layout keeps the diagonals and bands pixel-stable.
Content lengths are unknown (free-form presets), so every section measures
itself and page-breaks onto a slim continuation header when needed.
"""

import io
import os

from PIL import Image as PILImage

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.utils import simpleSplit

from app import database as db
from app.pdf_generator import (
    _register_fonts, _get_doc_data, get_output_dir, _safe_filename,
)

PAGE_W, PAGE_H = A4
M = 11 * mm                     # side margin
BOTTOM = 8 * mm                # content floor before a page break

# --- Palette: near-black + bronze, matches the client's brand ---
BLACK = colors.HexColor("#141414")
GOLD = colors.HexColor("#b08d57")
GOLD_LIGHT = colors.HexColor("#c9a97c")
CREAM = colors.HexColor("#f3f0ea")
PAPER = colors.HexColor("#faf9f7")
BORDER = colors.HexColor("#e6e2da")
TEXT = colors.HexColor("#1a1a1a")
MUTED = colors.HexColor("#6e6a63")
WHITE = colors.white

_ASSET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "custom_assets", "tt")


def _asset(name):
    path = os.path.join(_ASSET_DIR, name)
    return path if os.path.exists(path) else None


def photos_dir():
    d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "preset_photos")
    os.makedirs(d, exist_ok=True)
    return d


# --- Formatting -------------------------------------------------------------

def _eur(value):
    """1234.5 -> '1 234,50' (Latvian style: space thousands, comma decimals)."""
    neg = value < 0
    whole, cents = divmod(round(abs(value) * 100), 100)
    s = f"{whole:,}".replace(",", " ")
    return f"{'-' if neg else ''}{s},{cents:02d}"


def _qty(value):
    """Trim trailing zeros: 1.0 -> '1', 2.5 -> '2,5'."""
    s = f"{value:.2f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


# --- Line icons -------------------------------------------------------------
# Tiny geometric icons drawn with strokes; s is the icon box size, (cx, cy)
# its center. Deliberately minimal so they read cleanly at 3-5mm.

def _icon(c, name, cx, cy, s, color=GOLD, lw=0.9):
    c.saveState()
    c.setStrokeColor(color)
    c.setFillColor(color)
    c.setLineWidth(lw)
    c.setLineCap(1)
    c.setLineJoin(1)
    h = s / 2.0
    if name == "ruler":               # slanted ruler with ticks
        c.saveState()
        c.translate(cx, cy)
        c.rotate(45)
        c.roundRect(-h, -s * 0.18, s, s * 0.36, s * 0.08, stroke=1, fill=0)
        for i in (-0.5, 0.0, 0.5):
            c.line(i * h, s * 0.18, i * h, s * 0.02)
        c.restoreState()
    elif name == "width":             # horizontal double arrow
        c.line(cx - h, cy, cx + h, cy)
        for sx in (-1, 1):
            c.line(cx + sx * h, cy, cx + sx * (h - s * 0.28), cy + s * 0.2)
            c.line(cx + sx * h, cy, cx + sx * (h - s * 0.28), cy - s * 0.2)
    elif name == "roller":            # paint roller
        c.roundRect(cx - h, cy + s * 0.08, s * 0.8, s * 0.38, s * 0.06, stroke=1, fill=0)
        c.line(cx - h + s * 0.8, cy + s * 0.27, cx + h, cy + s * 0.27)
        c.line(cx + h * 0.55, cy + s * 0.27, cx + h * 0.55, cy - s * 0.05)
        c.line(cx + h * 0.55, cy - s * 0.05, cx + h * 0.1, cy - s * 0.05)
        c.line(cx + h * 0.1, cy - s * 0.05, cx + h * 0.1, cy - h)
    elif name == "pane":              # glass pane
        c.roundRect(cx - s * 0.32, cy - h, s * 0.64, s, s * 0.06, stroke=1, fill=0)
        c.line(cx - s * 0.32, cy + s * 0.16, cx + s * 0.32, cy + s * 0.16)
        c.line(cx - s * 0.1, cy - s * 0.28, cx + s * 0.14, cy + s * 0.02)
    elif name == "droplet":
        p = c.beginPath()
        p.moveTo(cx, cy + h)
        p.curveTo(cx + s * 0.42, cy + s * 0.05, cx + s * 0.34, cy - h, cx, cy - h)
        p.curveTo(cx - s * 0.34, cy - h, cx - s * 0.42, cy + s * 0.05, cx, cy + h)
        c.drawPath(p, stroke=1, fill=0)
    elif name == "bulb":
        c.circle(cx, cy + s * 0.12, s * 0.32, stroke=1, fill=0)
        c.line(cx - s * 0.12, cy - s * 0.24, cx - s * 0.12, cy - s * 0.4)
        c.line(cx + s * 0.12, cy - s * 0.24, cx + s * 0.12, cy - s * 0.4)
        c.line(cx - s * 0.12, cy - s * 0.4, cx + s * 0.12, cy - s * 0.4)
        for ang in (-1, 0, 1):
            c.line(cx + ang * s * 0.34, cy + s * 0.5 - abs(ang) * s * 0.06,
                   cx + ang * s * 0.44, cy + s * 0.62 - abs(ang) * s * 0.08)
    elif name == "pen":               # pen at 45deg
        c.saveState()
        c.translate(cx, cy)
        c.rotate(-45)
        c.roundRect(-s * 0.12, -h * 0.9, s * 0.24, s * 0.95, s * 0.05, stroke=1, fill=0)
        c.line(-s * 0.12, -h * 0.45, s * 0.12, -h * 0.45)
        p = c.beginPath()
        p.moveTo(-s * 0.12, -h * 0.9)
        p.lineTo(0, -h * 1.12)
        p.lineTo(s * 0.12, -h * 0.9)
        c.drawPath(p, stroke=1, fill=0)
        c.restoreState()
    elif name == "shield":
        p = c.beginPath()
        p.moveTo(cx, cy + h)
        p.lineTo(cx + s * 0.38, cy + s * 0.28)
        p.curveTo(cx + s * 0.38, cy - s * 0.2, cx + s * 0.22, cy - s * 0.38, cx, cy - h)
        p.curveTo(cx - s * 0.22, cy - s * 0.38, cx - s * 0.38, cy - s * 0.2, cx - s * 0.38, cy + s * 0.28)
        p.close()
        c.drawPath(p, stroke=1, fill=0)
        c.line(cx - s * 0.14, cy, cx - s * 0.02, cy - s * 0.14)
        c.line(cx - s * 0.02, cy - s * 0.14, cx + s * 0.18, cy + s * 0.16)
    elif name == "calendar":
        c.roundRect(cx - h, cy - h * 0.8, s, s * 0.8, s * 0.08, stroke=1, fill=0)
        c.line(cx - h, cy + s * 0.08, cx + h, cy + s * 0.08)
        c.line(cx - s * 0.22, cy + h * 0.55, cx - s * 0.22, cy + h * 0.15)
        c.line(cx + s * 0.22, cy + h * 0.55, cx + s * 0.22, cy + h * 0.15)
        for px in (-0.22, 0.02, 0.26):
            c.rect(cx + px * s - 0.4, cy - s * 0.18, 0.8, 0.8, stroke=1, fill=1)
    elif name == "star":
        import math
        p = c.beginPath()
        for i in range(10):
            ang = math.pi / 2 + i * math.pi / 5
            r = h if i % 2 == 0 else h * 0.42
            x, y = cx + r * math.cos(ang), cy + r * math.sin(ang)
            (p.moveTo if i == 0 else p.lineTo)(x, y)
        p.close()
        c.drawPath(p, stroke=0, fill=1)
    elif name == "cart":
        c.line(cx - h, cy + s * 0.3, cx - s * 0.28, cy + s * 0.3)
        p = c.beginPath()
        p.moveTo(cx - s * 0.28, cy + s * 0.3)
        p.lineTo(cx - s * 0.14, cy - s * 0.1)
        p.lineTo(cx + s * 0.4, cy - s * 0.1)
        p.lineTo(cx + h, cy + s * 0.24)
        c.drawPath(p, stroke=1, fill=0)
        c.circle(cx - s * 0.02, cy - s * 0.32, s * 0.09, stroke=1, fill=1)
        c.circle(cx + s * 0.3, cy - s * 0.32, s * 0.09, stroke=1, fill=1)
    elif name == "calc":
        c.roundRect(cx - s * 0.36, cy - h, s * 0.72, s, s * 0.08, stroke=1, fill=0)
        c.rect(cx - s * 0.22, cy + s * 0.14, s * 0.44, s * 0.22, stroke=1, fill=0)
        for ry in (-0.3, -0.06):
            for rx in (-0.22, 0.0, 0.22):
                c.rect(cx + rx * s - 0.5, cy + ry * s - 0.5, 1.0, 1.0, stroke=0, fill=1)
    elif name == "clipboard":
        c.roundRect(cx - s * 0.34, cy - h, s * 0.68, s * 0.92, s * 0.08, stroke=1, fill=0)
        c.roundRect(cx - s * 0.14, cy + s * 0.32, s * 0.28, s * 0.18, s * 0.04, stroke=1, fill=0)
        c.line(cx - s * 0.18, cy + s * 0.06, cx + s * 0.18, cy + s * 0.06)
        c.line(cx - s * 0.18, cy - s * 0.1, cx + s * 0.18, cy - s * 0.1)
        c.line(cx - s * 0.18, cy - s * 0.26, cx + s * 0.06, cy - s * 0.26)
    elif name == "camera":
        c.roundRect(cx - h, cy - s * 0.34, s, s * 0.68, s * 0.08, stroke=1, fill=0)
        c.circle(cx, cy - s * 0.02, s * 0.18, stroke=1, fill=0)
        c.line(cx - s * 0.2, cy + s * 0.34, cx - s * 0.1, cy + s * 0.46)
        c.line(cx - s * 0.1, cy + s * 0.46, cx + s * 0.1, cy + s * 0.46)
        c.line(cx + s * 0.1, cy + s * 0.46, cx + s * 0.2, cy + s * 0.34)
    elif name == "person":
        c.circle(cx, cy + s * 0.22, s * 0.2, stroke=1, fill=0)
        p = c.beginPath()
        p.moveTo(cx - s * 0.36, cy - h)
        p.curveTo(cx - s * 0.3, cy - s * 0.05, cx + s * 0.3, cy - s * 0.05, cx + s * 0.36, cy - h)
        c.drawPath(p, stroke=1, fill=0)
    elif name == "phone":
        c.saveState()
        c.translate(cx, cy)
        c.rotate(-30)
        c.roundRect(-s * 0.16, -h * 0.85, s * 0.32, s * 0.85, s * 0.09, stroke=1, fill=0)
        c.line(-s * 0.06, -h * 0.62, s * 0.06, -h * 0.62)
        c.restoreState()
    elif name == "globe":
        c.circle(cx, cy, h * 0.85, stroke=1, fill=0)
        c.ellipse(cx - h * 0.38, cy - h * 0.85, cx + h * 0.38, cy + h * 0.85, stroke=1, fill=0)
        c.line(cx - h * 0.85, cy, cx + h * 0.85, cy)
    elif name == "doc":
        c.roundRect(cx - s * 0.32, cy - h, s * 0.64, s, s * 0.06, stroke=1, fill=0)
        c.line(cx - s * 0.16, cy + s * 0.18, cx + s * 0.16, cy + s * 0.18)
        c.line(cx - s * 0.16, cy, cx + s * 0.16, cy)
        c.line(cx - s * 0.16, cy - s * 0.18, cx + s * 0.02, cy - s * 0.18)
    elif name == "percent":
        c.line(cx - s * 0.3, cy - s * 0.3, cx + s * 0.3, cy + s * 0.3)
        c.circle(cx - s * 0.26, cy + s * 0.26, s * 0.13, stroke=1, fill=0)
        c.circle(cx + s * 0.26, cy - s * 0.26, s * 0.13, stroke=1, fill=0)
    elif name == "building":
        c.rect(cx - s * 0.36, cy - h, s * 0.72, s, stroke=1, fill=0)
        c.line(cx - s * 0.16, cy + s * 0.2, cx + s * 0.16, cy + s * 0.2)
        c.line(cx - s * 0.16, cy, cx + s * 0.16, cy)
        c.rect(cx - s * 0.09, cy - h, s * 0.18, s * 0.26, stroke=1, fill=0)
    else:                             # "check" fallback
        c.line(cx - s * 0.32, cy, cx - s * 0.06, cy - s * 0.26)
        c.line(cx - s * 0.06, cy - s * 0.26, cx + s * 0.36, cy + s * 0.26)
    c.restoreState()


def _spec_icon(label):
    lo = (label or "").lower()
    for words, icon in (
        (("garum",), "ruler"), (("platum", "izmēr"), "width"),
        (("tonis", "krās", "ral"), "roller"),
        (("stikl", "jumt", "segum"), "pane"),
        (("ūdens", "notek", "lietus"), "droplet"),
        (("led", "apgaismo", "gaism"), "bulb"),
        (("garantij", "drošī"), "shield"),
        (("termiņ", "dien", "nedēļ"), "calendar"),
    ):
        if any(w in lo for w in words):
            return icon
    return "check"


def _benefit_icon(title):
    lo = (title or "").lower()
    for words, icon in (
        (("individuāl", "risinājum", "projekt"), "pen"),
        (("stikl", "rūdīt"), "pane"),
        (("ūdens", "notek",), "droplet"),
        (("cena", "dien", "spēkā"), "calendar"),
        (("garantij", "drošī", "izturīg"), "shield"),
        (("gaism", "led"), "bulb"),
    ):
        if any(w in lo for w in words):
            return icon
    return "star"


# --- Image helpers ----------------------------------------------------------

def _cover_jpeg(path, box_w_pt, box_h_pt):
    """Center-crop an image to the box aspect and downscale to ~2x display
    resolution; returns an ImageReader over a JPEG buffer (small to embed)."""
    img = PILImage.open(path).convert("RGB")
    target = box_w_pt / box_h_pt
    w, h = img.size
    if w / h > target:                      # too wide -> crop sides
        new_w = int(h * target)
        x0 = (w - new_w) // 2
        img = img.crop((x0, 0, x0 + new_w, h))
    else:                                   # too tall -> crop top/bottom
        new_h = int(w / target)
        y0 = (h - new_h) // 2
        img = img.crop((0, y0, w, y0 + new_h))
    max_px = max(200, int(box_w_pt / 72 * 96 * 2))
    if img.width > max_px:
        img = img.resize((max_px, round(img.height * max_px / img.width)),
                         PILImage.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=82)
    buf.seek(0)
    return ImageReader(buf)


_BEZIER_K = 0.5523              # quarter-circle cubic approximation


def _round_corners(c, x, y, w, h, r, bg=colors.white):
    """Paint bg-colored corner patches over a just-drawn rectangle image,
    faking rounded corners without an alpha channel (keeps photos as JPEG)."""
    k = _BEZIER_K * r
    c.saveState()
    c.setFillColor(bg)
    for cx, cy, dx, dy in ((x, y, 1, 1), (x + w, y, -1, 1),
                           (x + w, y + h, -1, -1), (x, y + h, 1, -1)):
        p = c.beginPath()
        p.moveTo(cx, cy)
        p.lineTo(cx, cy + dy * r)
        p.curveTo(cx, cy + dy * (r - k), cx + dx * (r - k), cy, cx + dx * r, cy)
        p.close()
        c.drawPath(p, stroke=0, fill=1)
    c.restoreState()


# --- Text helpers -----------------------------------------------------------

def _fit_font(text, font, size, max_width, min_size=6.5):
    while size > min_size and stringWidth(text, font, size) > max_width:
        size -= 0.5
    return size


def _ellipsize(text, font, size, max_width):
    if stringWidth(text, font, size) <= max_width:
        return text
    while text and stringWidth(text + "…", font, size) > max_width:
        text = text[:-1]
    return text + "…"


# --- Layout engine ----------------------------------------------------------

class _Page:
    """y-cursor page state; y measures down from the top edge in points."""

    def __init__(self, c, fonts, doc_label):
        self.c = c
        self.font, self.font_bold = fonts
        self.doc_label = doc_label
        self.num = 1
        self.y = 0

    def ensure(self, needed):
        if PAGE_H - self.y - needed < BOTTOM:
            self.break_page()
            return True
        return False

    def break_page(self):
        c = self.c
        c.showPage()
        self.num += 1
        # Slim continuation header: black band, small logo, doc reference
        band_h = 13 * mm
        c.setFillColor(BLACK)
        c.rect(0, PAGE_H - band_h, PAGE_W, band_h, stroke=0, fill=1)
        logo = _asset("logo_white.png")
        if logo:
            img = ImageReader(logo)
            iw, ih = img.getSize()
            lw = 26 * mm
            lh = lw * ih / iw
            c.drawImage(img, M, PAGE_H - band_h / 2 - lh / 2, lw, lh,
                        mask="auto")
        c.setFillColor(GOLD_LIGHT)
        c.setFont(self.font, 8)
        c.drawRightString(PAGE_W - M, PAGE_H - band_h / 2 - 2.8,
                          self.doc_label)
        self.y = band_h + 8 * mm

    def top(self):
        return PAGE_H - self.y          # current baseline origin (pt from bottom)


# --- Sections ---------------------------------------------------------------

HEADER_H = 42 * mm                      # straight part of the black band
HEADER_DIAG = 10 * mm                   # extra drop of the diagonal on the left


def _draw_header(pg, data):
    c = pg.c
    settings = data["settings"]
    # Black band with a diagonal lower edge (deeper on the left, like the
    # roofline in the logo mirrored).
    p = c.beginPath()
    p.moveTo(0, PAGE_H)
    p.lineTo(PAGE_W, PAGE_H)
    p.lineTo(PAGE_W, PAGE_H - HEADER_H)
    p.lineTo(0, PAGE_H - HEADER_H - HEADER_DIAG)
    p.close()
    c.setFillColor(BLACK)
    c.drawPath(p, stroke=0, fill=1)
    # Gold hairline tracing the diagonal edge
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.1)
    c.line(0, PAGE_H - HEADER_H - HEADER_DIAG - 1.4,
           PAGE_W, PAGE_H - HEADER_H - 1.4)

    # Header photo: center column, cover-cropped to the straight band part
    photo = _asset("header.jpg")
    px0, px1 = 96 * mm, 150 * mm
    if photo:
        bw, bh = px1 - px0, HEADER_H
        img = PILImage.open(photo).convert("RGB")
        iw, ih = img.size
        target = bw / bh
        if iw / ih > target:
            nw = int(ih * target)
            x0 = (iw - nw) // 2
            img = img.crop((x0, 0, x0 + nw, ih))
        else:
            nh = int(iw / target)
            # Bias the crop toward the top — that's where the pergola is
            y0 = int((ih - nh) * 0.25)
            img = img.crop((0, y0, iw, y0 + nh))
        max_px = int(bw / 72 * 96 * 2)
        if img.width > max_px:
            img = img.resize((max_px, round(img.height * max_px / img.width)),
                             PILImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=82)
        buf.seek(0)
        c.drawImage(ImageReader(buf), px0, PAGE_H - HEADER_H, bw, bh)

    # Logo + tagline, left
    logo = _asset("logo_white.png")
    lx, lw = M + 2 * mm, 58 * mm
    if logo:
        img = ImageReader(logo)
        iw, ih = img.getSize()
        lh = lw * ih / iw
        c.drawImage(img, lx, PAGE_H - 9 * mm - lh, lw, lh, mask="auto")
        ty = PAGE_H - 9 * mm - lh - 4.6 * mm
    else:
        c.setFillColor(WHITE)
        c.setFont(pg.font_bold, 20)
        c.drawString(lx, PAGE_H - 20 * mm, settings.get("company_name", ""))
        ty = PAGE_H - 26 * mm
    tagline = (settings.get("offer_tagline", "") or "").strip()
    if tagline:
        c.setFillColor(colors.HexColor("#bdb6ab"))
        c.setFont(pg.font, 6.8)
        c.drawString(lx + 1 * mm, ty, " ".join(tagline.upper()))

    # Contact column, right — rows with icons; blank values are skipped
    rows = []
    if settings.get("company_name"):
        rows.append(("building", settings["company_name"]))
    if settings.get("vat_number"):
        rows.append(("doc", f"PVN Nr. {settings['vat_number']}"))
    if settings.get("reg_number"):
        rows.append(("clipboard", f"Reģ.Nr. {settings['reg_number']}"))
    if settings.get("company_phone"):
        rows.append(("phone", f"Mob. {settings['company_phone']}"))
    if settings.get("company_website"):
        rows.append(("globe", settings["company_website"]))
    rx = 156 * mm
    ry = PAGE_H - 7.5 * mm
    for icon, text in rows[:5]:
        c.setStrokeColor(colors.HexColor("#3a3a38"))
        c.setLineWidth(0.7)
        c.setFillColor(colors.HexColor("#232220"))
        c.roundRect(rx, ry - 5.4 * mm, 5.4 * mm, 5.4 * mm, 1.2 * mm,
                    stroke=1, fill=1)
        _icon(c, icon, rx + 2.7 * mm, ry - 2.7 * mm, 3.1 * mm,
              color=GOLD_LIGHT, lw=0.75)
        c.setFillColor(colors.HexColor("#e8e4dd"))
        size = _fit_font(text, pg.font, 8.2, PAGE_W - M - (rx + 8 * mm))
        c.setFont(pg.font, size)
        c.drawString(rx + 7.6 * mm, ry - 3.8 * mm, text)
        ry -= 6.6 * mm

    pg.y = HEADER_H + HEADER_DIAG + 5 * mm


def _draw_title_block(pg, data, meta):
    c = pg.c
    doc = data["doc"]
    kicker = (data["doc_type_label"] or "Piedāvājums").upper()
    title = (meta.get("title") or "").strip() or data["doc_type_label"]

    # Client card, right: measure first so the title can wrap around it
    card_w, card_h = 62 * mm, 19 * mm
    card_x = PAGE_W - M - card_w
    top = pg.top()

    c.setFillColor(TEXT)
    c.setFont(pg.font, 8.5)
    c.setFillColor(MUTED)
    ktext = "  ".join(kicker)          # letterspaced
    c.drawString(M, top - 3.2 * mm, ktext)

    title_max = card_x - M - 6 * mm
    tsize = _fit_font(title, pg.font_bold, 19, title_max * 1.9, min_size=13)
    tlines = simpleSplit(title, pg.font_bold, tsize, title_max)[:2]
    ty = top - 3.2 * mm - 8 * mm
    c.setFillColor(TEXT)
    for line in tlines:
        c.setFont(pg.font_bold, tsize)
        c.drawString(M, ty, line)
        ty -= tsize * 1.15
    # Gold rule under the title
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.6)
    c.line(M, ty + 1.5, M + 24 * mm, ty + 1.5)
    # Small doc reference: number + date (the mockup omits it; a real
    # piedāvājums should not)
    c.setFillColor(MUTED)
    c.setFont(pg.font, 8)
    c.drawString(M + 28 * mm, ty + 0.4, f"Nr. {doc['doc_number']}  ·  {data['display_date']}")

    # Client card
    card_y = top - card_h
    c.setFillColor(BLACK)
    c.roundRect(card_x, card_y, card_w, card_h, 2.6 * mm, stroke=0, fill=1)
    circ_x = card_x + 9.5 * mm
    circ_y = card_y + card_h / 2
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.0)
    c.circle(circ_x, circ_y, 5.6 * mm, stroke=1, fill=0)
    _icon(c, "person", circ_x, circ_y, 5.6 * mm, color=GOLD_LIGHT, lw=0.9)
    name = (data["buyer"]["name"] or "").strip() or "—"
    text_x = card_x + 18.5 * mm
    text_max = card_x + card_w - text_x - 3 * mm
    c.setFillColor(colors.HexColor("#b9b3a9"))
    c.setFont(pg.font, 7.6)
    c.drawString(text_x, circ_y + 2.4 * mm, "K L I E N T S")
    nsize = _fit_font(name, pg.font_bold, 14.5, text_max, min_size=8)
    c.setFillColor(WHITE)
    c.setFont(pg.font_bold, nsize)
    c.drawString(text_x, circ_y - 4.2 * mm, _ellipsize(name, pg.font_bold, nsize, text_max))

    used = max(card_h, (top - ty) + 2 * mm)
    pg.y += used + 4 * mm


def _box_heading(pg, x, y_top, text, icon):
    c = pg.c
    _icon(c, icon, x + 3 * mm, y_top - 3.6 * mm, 4.2 * mm, color=GOLD, lw=1.0)
    c.setFillColor(GOLD)
    c.setFont(pg.font_bold, 9)
    c.drawString(x + 7.5 * mm, y_top - 4.8 * mm, " ".join(text.upper()))


def _measure_spec_rows(pg, specs, inner_w):
    rows = []
    for spec in specs:
        label = (spec.get("label") or "").strip()
        value = (spec.get("value") or "").strip()
        if not label and not value:
            continue
        val_w = stringWidth(value, pg.font_bold, 9.5) if value else 0
        lab_max = inner_w - 8 * mm - (val_w + 3 * mm)
        lines = simpleSplit(label, pg.font, 9.5, max(lab_max, 20 * mm))[:2] or [""]
        h = max(7.2 * mm, len(lines) * 4.2 * mm + 3.4 * mm)
        rows.append((lines, value, h))
    return rows


def _measure_benefit_rows(pg, benefits, inner_w):
    rows = []
    text_w = inner_w - 13.5 * mm
    for b in benefits:
        title = (b.get("title") or "").strip()
        text = (b.get("text") or "").strip()
        if not title and not text:
            continue
        tlines = simpleSplit(title, pg.font_bold, 9.8, text_w)[:2] or [""]
        xlines = simpleSplit(text, pg.font, 8.2, text_w)[:3] if text else []
        h = max(10.5 * mm, len(tlines) * 4.4 * mm + len(xlines) * 3.7 * mm + 4.6 * mm)
        rows.append((tlines, xlines, title, h))
    return rows


def _draw_boxes(pg, meta):
    """Tehniskā specifikācija (left) + priekšrocības (right), side by side.
    Both boxes get the height of the taller one."""
    c = pg.c
    specs = meta.get("specs") or []
    benefits = meta.get("benefits") or []
    if not specs and not benefits:
        return

    gap = 5 * mm
    box_w = (PAGE_W - 2 * M - gap) / 2
    pad = 5 * mm
    head_h = 8.5 * mm

    spec_rows = _measure_spec_rows(pg, specs, box_w - 2 * pad)
    ben_rows = _measure_benefit_rows(pg, benefits, box_w - 2 * pad)

    left_h = head_h + sum(r[2] for r in spec_rows) + pad if spec_rows else 0
    pill_h = 8.6 * mm if ben_rows else 0
    right_h = head_h + sum(r[3] for r in ben_rows) + pill_h + pad if ben_rows else 0
    box_h = max(left_h, right_h)

    pg.ensure(box_h + 4 * mm)
    top = pg.top()

    if spec_rows:
        x = M
        c.setFillColor(colors.white)
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.9)
        c.roundRect(x, top - box_h, box_w, box_h, 3 * mm, stroke=1, fill=1)
        _box_heading(pg, x + pad, top - pad * 0.5, "Tehniskā specifikācija", "ruler")
        ry = top - head_h - pad * 0.4
        for i, (lines, value, h) in enumerate(spec_rows):
            cy = ry - h / 2
            _icon(c, _spec_icon(lines[0]), x + pad + 2.2 * mm, cy, 4.4 * mm,
                  color=colors.HexColor("#8a8a86"), lw=0.85)
            c.setFillColor(TEXT)
            c.setFont(pg.font, 9.5)
            ly = cy + (len(lines) - 1) * 2.1 * mm - 1.2 * mm
            for line in lines:
                c.drawString(x + pad + 7.5 * mm, ly, line)
                ly -= 4.2 * mm
            if value:
                c.setFont(pg.font_bold, 9.5)
                c.drawRightString(x + box_w - pad, cy - 1.2 * mm, value)
            if i < len(spec_rows) - 1:
                c.setStrokeColor(BORDER)
                c.setLineWidth(0.6)
                c.line(x + pad, ry - h, x + box_w - pad, ry - h)
            ry -= h

    if ben_rows:
        x = M + box_w + gap
        c.setFillColor(CREAM)
        c.roundRect(x, top - box_h, box_w, box_h, 3 * mm, stroke=0, fill=1)
        # Subtle gold corner accent (folded-corner triangle, top right)
        p = c.beginPath()
        p.moveTo(x + box_w - 14 * mm, top)
        p.lineTo(x + box_w, top)
        p.lineTo(x + box_w, top - 14 * mm)
        p.close()
        c.setFillColor(colors.HexColor("#e9e2d5"))
        c.drawPath(p, stroke=0, fill=1)
        _box_heading(pg, x + pad, top - pad * 0.5, "Piedāvājuma priekšrocības", "star")
        ry = top - head_h - pad * 0.4
        for i, (tlines, xlines, title, h) in enumerate(ben_rows):
            cy = ry - h / 2
            circ_x = x + pad + 4.4 * mm
            c.setStrokeColor(GOLD)
            c.setLineWidth(0.9)
            c.setFillColor(colors.white)
            c.circle(circ_x, cy, 4.6 * mm, stroke=1, fill=1)
            _icon(c, _benefit_icon(title), circ_x, cy, 4.6 * mm, color=GOLD, lw=0.85)
            tx = x + pad + 11 * mm
            ly = ry - 5.4 * mm
            c.setFillColor(TEXT)
            c.setFont(pg.font_bold, 9.8)
            for line in tlines:
                c.drawString(tx, ly, line)
                ly -= 4.4 * mm
            c.setFillColor(MUTED)
            c.setFont(pg.font, 8.2)
            for line in xlines:
                c.drawString(tx, ly, line)
                ly -= 3.7 * mm
            if i < len(ben_rows) - 1:
                c.setStrokeColor(colors.HexColor("#e2dccf"))
                c.setLineWidth(0.6)
                c.line(x + pad, ry - h, x + box_w - pad, ry - h)
            ry -= h
        # PREMIUM pill
        pill_w = 58 * mm
        pill_x = x + (box_w - pill_w) / 2
        pill_y = top - box_h + pad * 0.7
        c.setFillColor(colors.white)
        c.setStrokeColor(colors.HexColor("#d9cfbc"))
        c.setLineWidth(0.8)
        c.roundRect(pill_x, pill_y, pill_w, 6.6 * mm, 1.6 * mm, stroke=1, fill=1)
        _icon(c, "star", pill_x + 6 * mm, pill_y + 3.3 * mm, 3.4 * mm, color=GOLD)
        c.setFillColor(colors.HexColor("#8a6f45"))
        c.setFont(pg.font_bold, 7.6)
        c.drawCentredString(pill_x + pill_w / 2 + 3 * mm, pill_y + 2.1 * mm,
                            "P R E M I U M   R I S I N Ā J U M S")

    pg.y += box_h + 4 * mm


def _draw_items_table(pg, data):
    c = pg.c
    items = data["items"]
    W = PAGE_W - 2 * M
    # Column x positions (right-aligned numeric columns)
    col_qty = M + W * 0.62
    col_price = M + W * 0.80
    col_total = M + W - 4 * mm
    head_h = 9.5 * mm

    def table_header():
        top = pg.top()
        c.setFillColor(BLACK)
        c.roundRect(M, top - head_h, W, head_h, 2 * mm, stroke=0, fill=1)
        # Gold diagonal-cut square with the cart icon
        p = c.beginPath()
        p.moveTo(M, top)
        p.lineTo(M + 14 * mm, top)
        p.lineTo(M + 10 * mm, top - head_h)
        p.lineTo(M, top - head_h)
        p.close()
        c.saveState()
        cp = c.beginPath()
        cp.roundRect(M, top - head_h, W, head_h, 2 * mm)
        c.clipPath(cp, stroke=0, fill=0)
        c.setFillColor(GOLD)
        c.drawPath(p, stroke=0, fill=1)
        c.restoreState()
        _icon(c, "cart", M + 6 * mm, top - head_h / 2, 5.2 * mm, color=BLACK, lw=1.0)
        c.setFillColor(WHITE)
        c.setFont(pg.font_bold, 9.5)
        c.drawString(M + 17 * mm, top - head_h / 2 - 1.6 * mm,
                     "PRODUKTI UN PAKALPOJUMI")
        c.setFillColor(colors.HexColor("#b9b3a9"))
        c.setFont(pg.font, 8)
        c.drawRightString(col_qty, top - head_h / 2 - 1.4 * mm, "DAUDZUMS")
        c.drawRightString(col_price, top - head_h / 2 - 1.4 * mm, "CENA")
        c.drawRightString(col_total, top - head_h / 2 - 1.4 * mm, "SUMMA")
        pg.y += head_h + 1.5 * mm

    pg.ensure(head_h + 12 * mm)
    table_header()

    name_max = (col_qty - 22 * mm) - M
    for idx, item in enumerate(items):
        name = (item.get("product_name") or "").strip() or "—"
        lines = simpleSplit(name, pg.font, 9.8, name_max)[:2]
        row_h = max(8.0 * mm, len(lines) * 4.6 * mm + 3.4 * mm)
        if pg.ensure(row_h + 2 * mm):
            table_header()
        top = pg.top()
        cy = top - row_h / 2
        c.setFillColor(TEXT)
        c.setFont(pg.font, 9.8)
        ly = cy + (len(lines) - 1) * 2.3 * mm - 1.4 * mm
        for line in lines:
            c.drawString(M + 2 * mm, ly, line)
            ly -= 4.6 * mm
        included = item.get("included_in_price")
        c.setFont(pg.font, 9.3)
        c.drawRightString(col_qty, cy - 1.4 * mm,
                          f"{_qty(item['quantity'])} {item['unit']}")
        if included:
            c.setFillColor(MUTED)
            c.setFont(pg.font, 8.6)
            c.drawRightString(col_total, cy - 1.4 * mm, "Iekļauts cenā")
        else:
            c.setFillColor(TEXT)
            c.setFont(pg.font, 9.3)
            c.drawRightString(col_price, cy - 1.4 * mm,
                              _eur(item["price_per_unit"]))
            c.setFont(pg.font_bold, 9.3)
            c.drawRightString(col_total, cy - 1.4 * mm,
                              _eur(item["quantity"] * item["price_per_unit"]))
        if idx < len(items) - 1:
            c.setStrokeColor(BORDER)
            c.setLineWidth(0.6)
            c.line(M + 2 * mm, top - row_h, M + W - 2 * mm, top - row_h)
        pg.y += row_h
    pg.y += 4 * mm


def _draw_totals(pg, data):
    c = pg.c
    band_h = 22 * mm
    pg.ensure(band_h + 3 * mm)
    top = pg.top()
    W = PAGE_W - 2 * M

    c.setFillColor(BLACK)
    c.roundRect(M, top - band_h, W, band_h, 2.6 * mm, stroke=0, fill=1)
    # Gold diagonal segment on the left with the calculator icon
    c.saveState()
    cp = c.beginPath()
    cp.roundRect(M, top - band_h, W, band_h, 2.6 * mm)
    c.clipPath(cp, stroke=0, fill=0)
    p = c.beginPath()
    p.moveTo(M, top)
    p.lineTo(M + 30 * mm, top)
    p.lineTo(M + 20 * mm, top - band_h)
    p.lineTo(M, top - band_h)
    p.close()
    c.setFillColor(GOLD)
    c.drawPath(p, stroke=0, fill=1)
    c.restoreState()
    c.setStrokeColor(BLACK)
    c.setLineWidth(1.0)
    c.roundRect(M + 5.5 * mm, top - band_h / 2 - 5.5 * mm, 11 * mm, 11 * mm,
                1.6 * mm, stroke=1, fill=0)
    _icon(c, "calc", M + 11 * mm, top - band_h / 2, 7 * mm, color=BLACK, lw=1.0)

    tx_label = M + 38 * mm
    tx_val = M + W - 6 * mm
    show_vat = data["is_vat_payer"] and not data["reverse_charge"]
    if show_vat:
        c.setFillColor(colors.HexColor("#d5d0c8"))
        c.setFont(pg.font, 9.3)
        _icon(c, "doc", tx_label - 4.5 * mm, top - 6.2 * mm, 3.4 * mm,
              color=colors.HexColor("#8f897f"), lw=0.75)
        c.drawString(tx_label, top - 7.4 * mm, "Kopējā summa")
        c.drawRightString(tx_val, top - 7.4 * mm, _eur(data["subtotal"]))
        _icon(c, "percent", tx_label - 4.5 * mm, top - 11.6 * mm, 3.4 * mm,
              color=colors.HexColor("#8f897f"), lw=0.75)
        c.drawString(tx_label, top - 12.8 * mm, f"PVN {data['vat_rate']:.0f}%")
        c.drawRightString(tx_val, top - 12.8 * mm, _eur(data["vat_amount"]))
        c.setStrokeColor(colors.HexColor("#3a3936"))
        c.setLineWidth(0.7)
        c.line(tx_label - 8 * mm, top - 15.6 * mm, tx_val, top - 15.6 * mm)
        gy = top - 19.6 * mm
    else:
        if data["reverse_charge"]:
            c.setFillColor(colors.HexColor("#d5d0c8"))
            c.setFont(pg.font, 8.2)
            c.drawString(tx_label, top - 8 * mm,
                         "PVN 0% — apgrieztā maksāšana (PVN likuma 142. pants)")
        gy = top - band_h / 2 - 2.4 * mm
    c.setFillColor(WHITE)
    c.setFont(pg.font_bold, 12.5)
    c.drawString(tx_label, gy, "Kopējā summa" + (" -" if show_vat else ""))
    c.setFillColor(GOLD_LIGHT)
    c.setFont(pg.font_bold, 15)
    c.drawRightString(tx_val, gy, f"{_eur(data['total'])} €")

    pg.y += band_h + 4 * mm


def _draw_conditions(pg, meta, data):
    c = pg.c
    text = (meta.get("conditions") or "").strip()
    notes = (data["doc"].get("notes") or "").strip()
    body = "\n".join(t for t in (text, notes) if t)
    if not body:
        return
    W = PAGE_W - 2 * M
    lines = []
    for raw in body.splitlines():
        raw = raw.strip()
        if raw:
            lines.extend(simpleSplit(raw, pg.font, 9, W - 60 * mm))
    lines = lines[:6]
    box_h = max(12 * mm, 7.5 * mm + len(lines) * 4.2 * mm)
    pg.ensure(box_h + 3 * mm)
    top = pg.top()

    c.setFillColor(PAPER)
    c.setStrokeColor(BORDER)
    c.setLineWidth(0.9)
    c.roundRect(M, top - box_h, W, box_h, 2.6 * mm, stroke=1, fill=1)
    circ_x = M + 8.5 * mm
    circ_y = top - box_h / 2
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.9)
    c.setFillColor(colors.white)
    c.circle(circ_x, circ_y, 4.8 * mm, stroke=1, fill=1)
    _icon(c, "clipboard", circ_x, circ_y, 4.8 * mm, color=GOLD, lw=0.85)
    c.setFillColor(GOLD)
    c.setFont(pg.font_bold, 8.6)
    c.drawString(M + 16 * mm, top - 6.4 * mm, "P A P I L D U S   N O S A C Ī J U M I")
    ly = top - 11 * mm
    c.setFillColor(TEXT)
    c.setFont(pg.font, 9)
    for line in lines:
        c.drawString(M + 16 * mm, ly, line)
        ly -= 4.2 * mm
    # Faint TT monogram, right
    c.saveState()
    c.setFillColor(GOLD)
    try:
        c.setFillAlpha(0.3)
    except AttributeError:
        pass
    c.setFont(pg.font_bold, 22)
    c.drawRightString(M + W - 6 * mm, top - box_h / 2 - 3 * mm, "TT")
    c.restoreState()

    pg.y += box_h + 4 * mm


def _draw_photos(pg, meta):
    c = pg.c
    pdir = photos_dir()
    paths = []
    for fname in (meta.get("photos") or [])[:5]:
        # Filenames only — a path separator in a stored value must not
        # escape the photos directory.
        fname = os.path.basename(str(fname))
        fpath = os.path.join(pdir, fname)
        if os.path.exists(fpath):
            paths.append(fpath)
    if not paths:
        return
    W = PAGE_W - 2 * M
    gap = 3 * mm
    n = len(paths)
    ph_w = (W - gap * (n - 1)) / n
    ph_h = min(30 * mm, ph_w * 1.0)
    label_h = 6.5 * mm
    pg.ensure(label_h + ph_h)
    top = pg.top()

    # Label row: camera chip + FOTO PIEMĒRI + dotted rule
    c.setFillColor(BLACK)
    c.roundRect(M, top - 5.6 * mm, 5.6 * mm, 5.6 * mm, 1.2 * mm, stroke=0, fill=1)
    _icon(c, "camera", M + 2.8 * mm, top - 2.8 * mm, 3.4 * mm, color=WHITE, lw=0.75)
    c.setFillColor(TEXT)
    c.setFont(pg.font_bold, 9.5)
    c.drawString(M + 8 * mm, top - 4.2 * mm, "FOTO PIEMĒRI:")
    lbl_w = stringWidth("FOTO PIEMĒRI:", pg.font_bold, 9.5)
    c.setStrokeColor(colors.HexColor("#c9c4bb"))
    c.setLineWidth(0.8)
    c.setDash(1, 2.4)
    c.line(M + 11 * mm + lbl_w, top - 3 * mm, M + W, top - 3 * mm)
    c.setDash()

    py = top - label_h
    x = M
    for fpath in paths:
        try:
            img = _cover_jpeg(fpath, ph_w, ph_h)
            c.drawImage(img, x, py - ph_h, ph_w, ph_h)
            _round_corners(c, x, py - ph_h, ph_w, ph_h, 2 * mm)
        except Exception:
            pass
        x += ph_w + gap
    pg.y += label_h + ph_h


# --- Entry point ------------------------------------------------------------

def generate_branded_offer_pdf(doc_id):
    """Render the branded offer. Returns the PDF filepath.
    Falls back on ValueError if the document has no offer_meta."""
    import json as _json

    data = _get_doc_data(doc_id)
    doc = data["doc"]
    raw = doc.get("offer_meta") or ""
    try:
        meta = _json.loads(raw) if raw else {}
    except ValueError:
        meta = {}
    if not isinstance(meta, dict):
        meta = {}

    fonts = _register_fonts()
    output_dir = get_output_dir()
    filename = f"{_safe_filename(doc['doc_number'])}.pdf"
    filepath = os.path.join(output_dir, filename)

    c = rl_canvas.Canvas(filepath, pagesize=A4)
    c.setTitle(f"{data['doc_type_label']} {doc['doc_number']}")
    c.setLineJoin(1)

    pg = _Page(c, fonts, f"{data['doc_type_label']} Nr. {doc['doc_number']}")
    _draw_header(pg, data)
    _draw_title_block(pg, data, meta)
    _draw_boxes(pg, meta)
    _draw_items_table(pg, data)
    _draw_totals(pg, data)
    _draw_conditions(pg, meta, data)
    _draw_photos(pg, meta)

    c.save()
    return filepath
