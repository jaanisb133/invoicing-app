# Footer payment logos

The four **card marks** — `visa.svg`, `mastercard.svg`, `applepay.svg`,
`googlepay.svg` — are committed. They come from simple-icons under CC0-1.0; see
SOURCES.txt. They are monochrome and the footer tints them for the theme.

The four **provider marks** — EveryPay, SEB, Citadele, LHV — are not committed.
No public icon set carries them and they are not ours to redistribute, so they
are copied onto the server by hand.

A mark with no file here renders as its **name in text** on the footer and the
terms page. Nothing breaks, but the real logos are what SEB compliance expects,
so this directory should not stay empty.

## Expected filenames

    visa.svg        mastercard.svg   googlepay.svg   applepay.svg   (committed)
    everypay.webp   seb.jpg          citadele.jpg    lhv.svg        (copy in)

The extension matters — it is the filename `app/payment_logos.py` looks for. If
you have a mark in a different format, either convert it or change the `file`
entry in that module to match.

## Getting the files

The original source (a WordPress media library) returned 404 for all eight on
2026-08-04 — that is the failure this whole arrangement exists to prevent, and
why the card marks are committed rather than fetched.

For the four provider marks the right source is **EveryPay's merchant logo
pack**, available from the
merchant portal. It carries exactly these marks, correctly licensed, and is
what the SEB card-logo requirement refers to. Failing that, each brand's own
brand centre (Visa, Mastercard, Google Pay, Apple Pay) publishes the official
files.

## Installing them

Copy them straight in:

    scp visa.png ... root@server:/opt/vrekini/app/static/img/payments/
    systemctl restart vrekini

Or, if they are reachable over HTTP, put the URLs in `app/payment_logos.py`
and let the script fetch them:

    python3 scripts/fetch_payment_logos.py
    systemctl restart vrekini

Check what is in place:

    python3 scripts/fetch_payment_logos.py --check
