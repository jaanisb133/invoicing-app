"""Payment and bank logos shown in the public footer.

These used to be hotlinked straight from vnmedia.lv/wp-content/uploads/. A
WordPress media reshuffle there would silently break the card logos SEB
compliance requires, on every public page, with nothing in this repo to show
why. The files belong here instead.

The marks are third-party trademarks, so the actual image files are not
committed — they are fetched from the source with scripts/fetch_payment_logos.py
and served from app/static/img/payments/. Until a file is present the footer
falls back to the original remote URL, so deploying this change on its own
cannot make the footer worse than it already was.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_DIR = os.path.join(BASE_DIR, "static", "img", "payments")
STATIC_PREFIX = "/static/img/payments"

# (filename, alt, footer height, terms-page height, group, source URL)
# `group` splits the row: "card" = accepted payment methods, "provider" = the
# payment provider and its banks. A separator is drawn between the two.
PAYMENT_LOGOS = [
    {
        "file": "visa.png",
        "alt": "Visa",
        "height": 12,
        "height_lg": 24,
        "group": "card",
        "source": "https://vnmedia.lv/wp-content/uploads/2026/03/Visa_Brandmark_Blue_RGB_2021.png",
    },
    {
        "file": "mastercard.svg",
        "alt": "Mastercard",
        "height": 16,
        "height_lg": 28,
        "group": "card",
        "source": "https://vnmedia.lv/wp-content/uploads/2026/03/ma_symbol.svg",
    },
    {
        "file": "googlepay.png",
        "alt": "Google Pay",
        "height": 12,
        "height_lg": 24,
        "group": "card",
        "source": "https://vnmedia.lv/wp-content/uploads/2026/03/Google_Pay_Logo.svg.png",
    },
    {
        "file": "applepay.svg",
        "alt": "Apple Pay",
        "height": 12,
        "height_lg": 24,
        "group": "card",
        "source": "https://vnmedia.lv/wp-content/uploads/2026/03/Apple_Pay_Mark_RGB_041619.svg",
    },
    {
        "file": "everypay.webp",
        "alt": "EveryPay",
        "height": 11,
        "height_lg": 20,
        "group": "provider",
        "source": "https://vnmedia.lv/wp-content/uploads/2026/03/Our_logotype_626px.webp",
    },
    {
        "file": "seb.jpg",
        "alt": "SEB",
        "height": 14,
        "height_lg": 26,
        "group": "provider",
        "source": "https://vnmedia.lv/wp-content/uploads/2026/03/seb_k_45mm150dpi.jpg",
    },
    {
        "file": "citadele.jpg",
        "alt": "Citadele",
        "height": 14,
        "height_lg": 26,
        "group": "provider",
        "source": "https://vnmedia.lv/wp-content/uploads/2026/03/Citadele_logo_bg.jpg",
    },
    {
        "file": "lhv.svg",
        "alt": "LHV",
        "height": 12,
        "height_lg": 22,
        "group": "provider",
        "source": "https://vnmedia.lv/wp-content/uploads/2026/03/lhv-logo.svg",
    },
]


def local_path(logo):
    return os.path.join(LOGO_DIR, logo["file"])


def is_local(logo):
    path = local_path(logo)
    return os.path.isfile(path) and os.path.getsize(path) > 0


def footer_logos():
    """The footer's logo list, each with the URL to actually render.

    Resolved once at import time — files arrive during deploy and the app
    restarts after, so there is nothing to re-check per request.
    """
    resolved = []
    for logo in PAYMENT_LOGOS:
        entry = dict(logo)
        entry["self_hosted"] = is_local(logo)
        entry["url"] = (
            f"{STATIC_PREFIX}/{logo['file']}" if entry["self_hosted"] else logo["source"]
        )
        resolved.append(entry)
    return resolved


def missing_logos():
    """Files still being hotlinked because they are not on disk yet."""
    return [logo["file"] for logo in PAYMENT_LOGOS if not is_local(logo)]
