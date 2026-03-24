#!/usr/bin/env python3
"""
V-Rēķini Offline Launcher

Starts the invoicing app in offline mode — single user, no login,
no payments, no email, all features unlocked.

Usage:
    python run_offline.py

On first run, downloads required vendor assets (Chart.js, Flatpickr)
if internet is available.  After that, works fully offline.
"""

import os
import sys
import webbrowser
import urllib.request
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENDOR_DIR = os.path.join(BASE_DIR, "app", "static", "vendor")

VENDOR_FILES = {
    "chart.umd.min.js": "https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js",
    "flatpickr.min.js": "https://cdn.jsdelivr.net/npm/flatpickr@4.6.13/dist/flatpickr.min.js",
    "flatpickr.min.css": "https://cdn.jsdelivr.net/npm/flatpickr@4.6.13/dist/flatpickr.min.css",
}


def download_vendor_assets():
    """Download CDN assets for offline use.  Skips files that already exist."""
    os.makedirs(VENDOR_DIR, exist_ok=True)

    missing = {k: v for k, v in VENDOR_FILES.items()
               if not os.path.exists(os.path.join(VENDOR_DIR, k))}

    if not missing:
        return True

    print("Lejupielādē nepieciešamos failus (pirmā palaišana)...")
    for filename, url in missing.items():
        dest = os.path.join(VENDOR_DIR, filename)
        try:
            print(f"  {filename} ...", end=" ", flush=True)
            urllib.request.urlretrieve(url, dest)
            print("OK")
        except Exception as e:
            print(f"KĻŪDA: {e}")
            print(f"\nNeizdevās lejupielādēt {filename}.")
            print(f"Lūdzu manuāli lejupielādējiet no:\n  {url}")
            print(f"un saglabājiet kā:\n  {dest}")
            return False
    return True


def main():
    # Ensure vendor assets exist
    if not download_vendor_assets():
        print("\nPiezīme: Lietotne darbosies, bet diagrammas un "
              "datumu izvēle var nedarboties bez vendor failiem.")

    # Set offline mode
    os.environ["OFFLINE_MODE"] = "1"

    # Use a dedicated database file for the offline version
    data_dir = os.path.join(BASE_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)
    if "VREKINI_DB_PATH" not in os.environ:
        os.environ["VREKINI_DB_PATH"] = os.path.join(data_dir, "offline.db")

    port = int(os.environ.get("PORT", "8000"))

    print()
    print("╔══════════════════════════════════════════╗")
    print("║        V-Rēķini — Offline režīms         ║")
    print("╠══════════════════════════════════════════╣")
    print(f"║  Adrese: http://localhost:{port:<15s}   ║")
    print("║  Lai apturētu: Ctrl+C                    ║")
    print("╚══════════════════════════════════════════╝")
    print()

    # Open browser after a short delay
    def open_browser():
        time.sleep(1.5)
        webbrowser.open(f"http://localhost:{port}")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    # Start the server
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
