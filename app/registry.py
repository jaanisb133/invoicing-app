"""
Latvian Business Registry (Uzņēmumu reģistrs) — local search database.

Downloads the official open data CSV from dati.ur.gov.lv and imports it
into a separate SQLite database for fast company name/regcode lookups.

Data source: https://dati.ur.gov.lv/register/register.csv
License: Free for any use (commercial included), updated daily.
"""

import csv
import io
import os
import sqlite3
import urllib.request
import logging

logger = logging.getLogger(__name__)

REGISTRY_CSV_URL = "https://dati.ur.gov.lv/register/register.csv"

# Separate DB so the main app DB stays small and clean
_data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
REGISTRY_DB_PATH = os.environ.get(
    "VREKINI_REGISTRY_DB_PATH",
    os.path.join(_data_dir, "registry.db"),
)


def _get_conn():
    os.makedirs(os.path.dirname(REGISTRY_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(REGISTRY_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_registry_db():
    """Create the registry table and indexes if they don't exist."""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS businesses (
            regcode TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type_text TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            registered TEXT NOT NULL DEFAULT '',
            terminated TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_businesses_name ON businesses(name COLLATE NOCASE);
    """)
    conn.close()


def import_from_csv(csv_path=None):
    """
    Import businesses from the UR open data CSV into the local registry DB.
    If csv_path is None, downloads from the official URL.
    Returns the number of records imported.
    """
    init_registry_db()

    if csv_path is None:
        logger.info("Downloading registry CSV from %s ...", REGISTRY_CSV_URL)
        req = urllib.request.Request(REGISTRY_CSV_URL, headers={"User-Agent": "V-Rekini/1.0"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            raw = resp.read()
        # Try UTF-8 first, fall back to latin-1
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
    else:
        logger.info("Importing registry CSV from %s ...", csv_path)
        f = open(csv_path, "r", encoding="utf-8")
        try:
            reader = csv.DictReader(f, delimiter=";")
        except Exception:
            f.close()
            f = open(csv_path, "r", encoding="latin-1")
            reader = csv.DictReader(f, delimiter=";")

    conn = _get_conn()
    conn.execute("DELETE FROM businesses")

    batch = []
    count = 0
    for row in reader:
        regcode = (row.get("regcode") or "").strip()
        name = (row.get("name") or "").strip()
        if not regcode or not name:
            continue
        batch.append((
            regcode,
            name,
            (row.get("type_text") or row.get("type") or "").strip(),
            (row.get("address") or "").strip(),
            (row.get("registered") or "").strip(),
            (row.get("terminated") or "").strip(),
        ))
        if len(batch) >= 5000:
            conn.executemany(
                "INSERT OR REPLACE INTO businesses (regcode, name, type_text, address, registered, terminated) VALUES (?, ?, ?, ?, ?, ?)",
                batch,
            )
            count += len(batch)
            batch = []

    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO businesses (regcode, name, type_text, address, registered, terminated) VALUES (?, ?, ?, ?, ?, ?)",
            batch,
        )
        count += len(batch)

    conn.commit()
    conn.close()

    if csv_path and 'f' in dir():
        try:
            f.close()
        except Exception:
            pass

    logger.info("Imported %d businesses into registry DB.", count)
    return count


def search(query, limit=15):
    """
    Search businesses by name or registration number.
    Returns list of dicts with regcode, name, type_text, address.
    Only returns active businesses (no termination date).
    """
    if not query or len(query) < 2:
        return []

    conn = _get_conn()
    query = query.strip()

    # If query looks like a registration number (digits only), search by regcode
    if query.isdigit():
        rows = conn.execute(
            "SELECT regcode, name, type_text, address FROM businesses "
            "WHERE regcode LIKE ? AND terminated = '' LIMIT ?",
            (query + "%", limit),
        ).fetchall()
    else:
        # Search by name — prioritize starts-with, then contains
        rows = conn.execute(
            "SELECT regcode, name, type_text, address FROM businesses "
            "WHERE name LIKE ? AND terminated = '' "
            "ORDER BY CASE WHEN name LIKE ? THEN 0 ELSE 1 END, name "
            "LIMIT ?",
            ("%" + query + "%", query + "%", limit),
        ).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def get_record_count():
    """Return the number of businesses in the registry DB."""
    try:
        conn = _get_conn()
        row = conn.execute("SELECT COUNT(*) as cnt FROM businesses").fetchone()
        conn.close()
        return row["cnt"] if row else 0
    except Exception:
        return 0


# CLI entry point for manual import
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    csv_file = sys.argv[1] if len(sys.argv) > 1 else None
    count = import_from_csv(csv_file)
    print(f"Done. {count} businesses imported.")
