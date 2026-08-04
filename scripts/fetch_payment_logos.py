#!/usr/bin/env python3
"""Download the footer payment logos so they are served from our own domain.

The logos are third-party trademarks, so the files are not committed to the
repo. Run this once on the server after deploying, then restart the app:

    python3 scripts/fetch_payment_logos.py
    systemctl restart vrekini

Until a file is present the footer falls back to the original remote URL, so
running this is what actually stops the hotlinking — nothing breaks if you
forget, it just stays as it was.

Options:
    --force     re-download files that already exist
    --check     report status and exit without downloading
"""

import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.payment_logos import PAYMENT_LOGOS, LOGO_DIR, local_path, is_local  # noqa: E402

TIMEOUT = 30
# Some CDNs refuse the default urllib agent.
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; vrekini-asset-fetch/1.0)"}

# What each file must look like to be accepted, so a 404 HTML page or an error
# page never gets written out as though it were a logo.
SIGNATURES = {
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
    ".webp": [b"RIFF"],
    ".svg": [b"<svg", b"<?xml"],
}


def looks_valid(data, filename):
    if len(data) < 200:
        return False, f"only {len(data)} bytes"
    ext = os.path.splitext(filename)[1].lower()
    expected = SIGNATURES.get(ext)
    if not expected:
        return True, ""
    head = data[:512].lstrip()
    if any(head.startswith(sig) for sig in expected):
        return True, ""
    if ext == ".svg" and b"<svg" in data[:2048]:
        return True, ""
    return False, f"not a {ext[1:]} file (starts with {head[:16]!r})"


def fetch(logo, force=False):
    target = local_path(logo)
    if is_local(logo) and not force:
        return "skip", f"already present ({os.path.getsize(target)} bytes)"
    try:
        req = urllib.request.Request(logo["source"], headers=HEADERS)
        with urllib.request.urlopen(req, timeout=TIMEOUT) as response:
            data = response.read()
    except Exception as exc:
        return "fail", f"{type(exc).__name__}: {exc}"

    ok, why = looks_valid(data, logo["file"])
    if not ok:
        return "fail", why

    # Write via a temp file so an interrupted run cannot leave a half file that
    # is_local() would then treat as present.
    tmp = target + ".part"
    with open(tmp, "wb") as handle:
        handle.write(data)
    os.replace(tmp, target)
    return "ok", f"{len(data)} bytes"


def main():
    force = "--force" in sys.argv
    check_only = "--check" in sys.argv
    os.makedirs(LOGO_DIR, exist_ok=True)
    print(f"Target: {LOGO_DIR}\n")

    counts = {"ok": 0, "skip": 0, "fail": 0}
    for logo in PAYMENT_LOGOS:
        if check_only:
            state = "present" if is_local(logo) else "MISSING (hotlinked)"
            print(f"  {logo['file']:18} {state}")
            counts["ok" if is_local(logo) else "fail"] += 1
            continue
        status, detail = fetch(logo, force=force)
        counts[status] += 1
        mark = {"ok": "OK  ", "skip": "--  ", "fail": "FAIL"}[status]
        print(f"  {mark} {logo['file']:18} {detail}")

    print()
    if check_only:
        print(f"{counts['ok']}/{len(PAYMENT_LOGOS)} self-hosted")
        return 0 if counts["fail"] == 0 else 1

    print(f"downloaded {counts['ok']}, skipped {counts['skip']}, failed {counts['fail']}")
    if counts["fail"]:
        print("\nFailed files stay hotlinked. Fix the source URL in "
              "app/payment_logos.py, or drop the entry if the method is not "
              "actually offered at checkout.")
    else:
        print("\nAll logos self-hosted. Restart the app to pick them up.")
    return 1 if counts["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
