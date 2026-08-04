"""Payment and bank logos shown in the public footer.

These used to be hotlinked straight from vnmedia.lv/wp-content/uploads/. A
WordPress media reshuffle there would silently break the card logos SEB
compliance requires, on every public page, with nothing in this repo to show
why. The files belong here instead.

The four card marks (Visa, Mastercard, Apple Pay, Google Pay) ship with the
repo, from simple-icons under CC0-1.0 — see static/img/payments/SOURCES.txt.
Committing them reverses the original plan of fetching at deploy time: that
plan depended on a URL staying alive, and the first time it was exercised all
eight sources returned 404. A file in git cannot 404.

The provider marks (EveryPay, SEB, Citadele, LHV) are in no public icon set and
are not ours to redistribute, so they are still copied in by hand. A mark with
no file renders as its name in text — never as a remote <img>, because the old
sources are dead and a broken image on every public page is worse than a word.
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_DIR = os.path.join(BASE_DIR, "static", "img", "payments")
STATIC_PREFIX = "/static/img/payments"

# (filename, alt, footer height, terms-page height, mono?, group, source URL)
# `mono` marks a single-colour glyph the footer has to tint for the theme.
# `group` splits the row: "card" = accepted payment methods, "provider" = the
# payment provider and its banks. A separator is drawn between the two.
PAYMENT_LOGOS = [
    {
        "file": "visa.svg",
        "alt": "Visa",
        "height": 14,
        "height_lg": 26,
        "mono": True,
        "group": "card",
        "source": "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/visa.svg",
    },
    {
        "file": "mastercard.svg",
        "alt": "Mastercard",
        "height": 16,
        "height_lg": 28,
        "mono": True,
        "group": "card",
        "source": "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/mastercard.svg",
    },
    {
        "file": "googlepay.svg",
        "alt": "Google Pay",
        "height": 14,
        "height_lg": 26,
        "mono": True,
        "group": "card",
        "source": "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/googlepay.svg",
    },
    {
        "file": "applepay.svg",
        "alt": "Apple Pay",
        "height": 14,
        "height_lg": 26,
        "mono": True,
        "group": "card",
        "source": "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/applepay.svg",
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
    """Files still being hotlinked because they are not on disk yet."""
    return [logo["file"] for logo in PAYMENT_LOGOS if not is_local(logo)]
