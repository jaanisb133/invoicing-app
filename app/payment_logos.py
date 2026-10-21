"""Payment and bank logos shown in the public footer and on the terms page.

These used to be hotlinked straight from vnmedia.lv/wp-content/uploads/. A
WordPress media reshuffle there broke them silently (every URL 404'd on
2026-08-04), on every public page, with nothing in this repo to show why. SEB
compliance requires the card marks, so the files now live in the repo instead.

All of them are the merchant's official artwork — see
static/img/payments/SOURCES.txt. A mark with no file renders as its name in
text, never as a remote <img>: a broken image on every public page is worse
than a word.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_DIR = os.path.join(BASE_DIR, "static", "img", "payments")
STATIC_PREFIX = "/static/img/payments"

# `height` / `height_lg`: footer and terms-page heights in px, set per mark so
# they read at the same optical size rather than fill the same box.
# `source`: an optional URL for scripts/fetch_payment_logos.py; empty = copied in.
# `group` splits the row: "card" = accepted payment methods, "provider" = the
# payment provider and its banks. A separator is drawn between the two.
PAYMENT_LOGOS = [
    {"file": "visa.png", "alt": "Visa", "height": 12, "height_lg": 22, "group": "card", "source": ""},
    {"file": "mastercard.png", "alt": "Mastercard", "height": 18, "height_lg": 30, "group": "card", "source": ""},
    {"file": "googlepay.png", "alt": "Google Pay", "height": 20, "height_lg": 32, "group": "card", "source": ""},
    {"file": "applepay.svg", "alt": "Apple Pay", "height": 20, "height_lg": 32, "group": "card", "source": ""},
    {"file": "everypay.webp", "alt": "EveryPay", "height": 12, "height_lg": 22, "group": "provider", "source": ""},
    {"file": "seb.png", "alt": "SEB", "height": 14, "height_lg": 26, "group": "provider", "source": ""},
    {"file": "swedbank.webp", "alt": "Swedbank", "height": 16, "height_lg": 28, "group": "provider", "source": ""},
    {"file": "citadele.png", "alt": "Citadele", "height": 16, "height_lg": 28, "group": "provider", "source": ""},
    {"file": "lhv.svg", "alt": "LHV", "height": 11, "height_lg": 20, "group": "provider", "source": ""},
]


def local_path(logo):
    return os.path.join(LOGO_DIR, logo["file"])


def is_local(logo):
    path = local_path(logo)
    return os.path.isfile(path) and os.path.getsize(path) > 0


def footer_logos():
    """The footer's logo list, each with the URL to actually render.

    Resolved once at import time — files arrive during deploy and the app
    restarts after, so there is nothing to re-check per request. A logo with no
    file gets url=None and is rendered as text by the templates.
    """
    resolved = []
    for logo in PAYMENT_LOGOS:
        entry = dict(logo)
        entry["self_hosted"] = is_local(logo)
        # No remote fallback: the source URLs are dead, and a broken image is
        # worse than the mark's name in text.
        entry["url"] = f"{STATIC_PREFIX}/{logo['file']}" if entry["self_hosted"] else None
        resolved.append(entry)
    return resolved


def missing_logos():
    """Marks with no file on disk, rendered as text."""
    return [logo["file"] for logo in PAYMENT_LOGOS if not is_local(logo)]
