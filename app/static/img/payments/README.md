# Footer payment logos

These files are **not committed** — they are third-party trademarks (Visa,
Mastercard, Google Pay, Apple Pay, EveryPay, SEB, Citadele, LHV) and belong to
their owners. The repo carries the manifest, not the artwork.

Populate this directory on the server:

    python3 scripts/fetch_payment_logos.py
    systemctl restart vrekini

Check what is self-hosted vs still hotlinked:

    python3 scripts/fetch_payment_logos.py --check

The list of logos, their sizes and their source URLs live in
`app/payment_logos.py`. Add, remove or re-point a logo there — never paste a
URL into the footer template.

Until a file exists here the footer falls back to its original remote URL, so a
deploy without running the script changes nothing. The app logs a warning at
startup naming every logo still being hotlinked.
