"""Latvian number formatting, shared by templates, PDFs and e-mails.

1955.84 -> "1 955,84 €": a space between thousands, a comma before the
decimals. The spaces are non-breaking so an amount never wraps across lines.
Machine formats (e-invoice XML, CSV for accounting) keep plain dots and do not
use these helpers.
"""

NBSP = " "


def num(value, decimals=2):
    """1234.5 -> '1 234,50'. None or junk prints as 0."""
    try:
        value = float(value or 0)
    except (TypeError, ValueError):
        value = 0.0
    neg = value < 0 and round(abs(value), decimals) != 0
    s = f"{abs(value):,.{decimals}f}"
    whole, _, frac = s.partition(".")
    out = whole.replace(",", NBSP)
    if decimals:
        out += "," + frac
    return ("-" if neg else "") + out


def eur(value):
    """1955.84 -> '1 955,84 €'."""
    return num(value) + NBSP + "€"


def qty(value):
    """Quantities drop trailing zeros: 120.0 -> '120', 2.5 -> '2,5', 0.65 -> '0,65'."""
    s = num(value, 2)
    if "," in s:
        s = s.rstrip("0").rstrip(",")
    return s


def parse_decimal(raw, default=0.0):
    """Read a number typed the Latvian way ('1 234,50') or the dot way ('1234.50')."""
    if raw is None:
        return default
    s = str(raw).strip().replace(NBSP, "").replace(" ", "").replace("€", "")
    if not s:
        return default
    if "," in s and "." in s:
        # Whichever separator comes last is the decimal one.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(",", ".")
    return float(s)
