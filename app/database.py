"""
Database module for Pavadzīmju Pārvaldnieks (Web).
Adapted from desktop/database.py for the FastAPI web application.
Handles SQLite database creation, migrations, and all CRUD operations.
"""

import sqlite3
import os
import datetime

DB_NAME = "veggie_invoices.db"

_db_dir = os.path.dirname(os.path.abspath(__file__))
_db_path = os.path.join(os.path.dirname(_db_dir), "data", DB_NAME)


def get_db_path():
    """Get the database path in the data/ directory."""
    data_dir = os.path.dirname(_db_path)
    os.makedirs(data_dir, exist_ok=True)
    return _db_path


def get_connection():
    """Get a database connection with foreign keys enabled."""
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            unit TEXT NOT NULL DEFAULT 'kg',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            reg_number TEXT,
            vat_number TEXT,
            legal_address TEXT,
            bank_name TEXT,
            bank_account TEXT,
            contact_person TEXT,
            phone TEXT,
            email TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_type TEXT NOT NULL CHECK(doc_type IN ('buy', 'sell')),
            doc_number TEXT NOT NULL,
            client_id INTEGER NOT NULL,
            doc_date DATE NOT NULL,
            vat_rate REAL NOT NULL DEFAULT 21.0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        );

        CREATE TABLE IF NOT EXISTS document_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            price_per_unit REAL NOT NULL,
            total REAL NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id)
        );

        CREATE TABLE IF NOT EXISTS doc_sequences (
            prefix TEXT PRIMARY KEY,
            last_number INTEGER NOT NULL DEFAULT 0,
            year INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS recycled_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_type TEXT NOT NULL,
            year INTEGER NOT NULL,
            number INTEGER NOT NULL,
            recycled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()


# --- Settings ---

def get_setting(key, default=""):
    conn = get_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key, value):
    conn = get_connection()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
        (key, value, value)
    )
    conn.commit()
    conn.close()


def get_all_settings():
    """Get all settings as a dictionary."""
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}


def save_all_settings(settings_dict):
    """Save multiple settings at once."""
    conn = get_connection()
    for key, value in settings_dict.items():
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
            (key, value, value)
        )
    conn.commit()
    conn.close()


# --- Products ---

def add_product(name, unit):
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO products (name, unit) VALUES (?, ?)",
        (name, unit)
    )
    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return product_id


def update_product(product_id, name, unit):
    conn = get_connection()
    conn.execute(
        "UPDATE products SET name = ?, unit = ? WHERE id = ?",
        (name, unit, product_id)
    )
    conn.commit()
    conn.close()


def delete_product(product_id):
    """Soft delete - mark as inactive."""
    conn = get_connection()
    conn.execute("UPDATE products SET active = 0 WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()


def get_all_products(active_only=True):
    conn = get_connection()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM products WHERE active = 1 ORDER BY name"
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM products ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product(product_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# --- Clients ---

def add_client(name, reg_number="", vat_number="", legal_address="",
               bank_name="", bank_account="", contact_person="", phone="", email=""):
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO clients (name, reg_number, vat_number, legal_address,
           bank_name, bank_account, contact_person, phone, email)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, reg_number, vat_number, legal_address,
         bank_name, bank_account, contact_person, phone, email)
    )
    client_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return client_id


def update_client(client_id, **kwargs):
    allowed_fields = {"name", "reg_number", "vat_number", "legal_address",
                      "bank_name", "bank_account", "contact_person", "phone", "email"}
    conn = get_connection()
    for key, value in kwargs.items():
        if key in allowed_fields:
            conn.execute(f"UPDATE clients SET {key} = ? WHERE id = ?", (value, client_id))
    conn.commit()
    conn.close()


def delete_client(client_id):
    """Soft delete - mark as inactive."""
    conn = get_connection()
    conn.execute("UPDATE clients SET active = 0 WHERE id = ?", (client_id,))
    conn.commit()
    conn.close()


def get_all_clients(active_only=True):
    conn = get_connection()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM clients WHERE active = 1 ORDER BY name"
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM clients ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_client(client_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# --- Documents ---

def get_next_doc_number(doc_type, year, conn=None):
    """
    Get next sequential document number.
    Uses recycled numbers first, then increments sequence.
    """
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    if doc_type == "buy":
        prefix = get_setting("buy_doc_prefix", "PIR")
    else:
        prefix = get_setting("sell_doc_prefix", "PAR")

    seq_key = f"{doc_type}-{year}"

    recycled = conn.execute(
        "SELECT id, number FROM recycled_numbers WHERE doc_type = ? AND year = ? ORDER BY number ASC LIMIT 1",
        (doc_type, year)
    ).fetchone()

    if recycled:
        next_num = recycled["number"]
        conn.execute("DELETE FROM recycled_numbers WHERE id = ?", (recycled["id"],))
    else:
        row = conn.execute(
            "SELECT last_number FROM doc_sequences WHERE prefix = ? AND year = ?",
            (seq_key, year)
        ).fetchone()

        if row:
            next_num = row["last_number"] + 1
            conn.execute(
                "UPDATE doc_sequences SET last_number = ? WHERE prefix = ?",
                (next_num, seq_key)
            )
        else:
            next_num = 1
            conn.execute(
                "INSERT INTO doc_sequences (prefix, last_number, year) VALUES (?, ?, ?)",
                (seq_key, next_num, year)
            )

    if close_conn:
        conn.commit()
        conn.close()

    return f"{prefix}-{year}-{next_num:04d}", next_num


def create_document(doc_type, client_id, doc_date, items, vat_rate=21.0, notes=""):
    """
    Create a document with line items.
    items: list of dicts with keys: product_id, quantity, unit, price_per_unit
    Returns (document_id, doc_number) or raises ValueError if stock insufficient.
    """
    year = doc_date.year if isinstance(doc_date, datetime.date) else int(doc_date[:4])

    conn = get_connection()
    try:
        if doc_type == "sell":
            for item in items:
                available = _get_product_stock(conn, item["product_id"])
                product = get_product(item["product_id"])
                if item["quantity"] > available:
                    product_name = product["name"] if product else f"ID:{item['product_id']}"
                    raise ValueError(
                        f"Nepietiekams daudzums: {product_name}. "
                        f"Pieejams: {available:.2f}, pieprasīts: {item['quantity']:.2f}"
                    )

        doc_number, seq_num = get_next_doc_number(doc_type, year, conn)

        cursor = conn.execute(
            """INSERT INTO documents (doc_type, doc_number, client_id, doc_date, vat_rate, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (doc_type, doc_number, client_id,
             doc_date if isinstance(doc_date, str) else doc_date.isoformat(),
             vat_rate, notes)
        )
        doc_id = cursor.lastrowid

        for item in items:
            total = item["quantity"] * item["price_per_unit"]
            conn.execute(
                """INSERT INTO document_items (document_id, product_id, quantity, unit, price_per_unit, total)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (doc_id, item["product_id"], item["quantity"], item["unit"],
                 item["price_per_unit"], total)
            )

        conn.commit()
        return doc_id, doc_number
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_document(doc_id):
    conn = get_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    items = conn.execute(
        """SELECT di.*, p.name as product_name
           FROM document_items di
           JOIN products p ON di.product_id = p.id
           WHERE di.document_id = ?""",
        (doc_id,)
    ).fetchall()
    conn.close()
    return (dict(doc) if doc else None, [dict(i) for i in items])


def get_documents(doc_type=None, client_id=None, date_from=None, date_to=None):
    """Get documents with optional filters."""
    conn = get_connection()
    query = """SELECT d.*, c.name as client_name
               FROM documents d
               JOIN clients c ON d.client_id = c.id
               WHERE 1=1"""
    params = []

    if doc_type:
        query += " AND d.doc_type = ?"
        params.append(doc_type)
    if client_id:
        query += " AND d.client_id = ?"
        params.append(client_id)
    if date_from:
        query += " AND d.doc_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND d.doc_date <= ?"
        params.append(date_to)

    query += " ORDER BY d.doc_date DESC, d.id DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_document(doc_id):
    """Delete a document, its items, and recycle the document number."""
    conn = get_connection()
    doc = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if doc:
        parts = doc["doc_number"].rsplit("-", 1)
        if len(parts) == 2:
            try:
                seq_num = int(parts[1])
                year = int(doc["doc_date"][:4])
                conn.execute(
                    "INSERT INTO recycled_numbers (doc_type, year, number) VALUES (?, ?, ?)",
                    (doc["doc_type"], year, seq_num)
                )
            except (ValueError, IndexError):
                pass

    conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    conn.commit()
    conn.close()


# --- Stock ---

def _get_product_stock(conn, product_id):
    """Get current stock for a product (internal, uses existing connection)."""
    row = conn.execute("""
        SELECT
            COALESCE(
                (SELECT SUM(di.quantity) FROM document_items di
                 JOIN documents d ON di.document_id = d.id
                 WHERE di.product_id = ? AND d.doc_type = 'buy'), 0
            ) -
            COALESCE(
                (SELECT SUM(di.quantity) FROM document_items di
                 JOIN documents d ON di.document_id = d.id
                 WHERE di.product_id = ? AND d.doc_type = 'sell'), 0
            ) as stock
    """, (product_id, product_id)).fetchone()
    return row["stock"] if row else 0


def get_stock(date_from=None, date_to=None):
    """Get stock levels for all active products, optionally filtered by date range."""
    conn = get_connection()

    date_filter = ""
    params_buy = []
    params_sell = []

    if date_from:
        date_filter += " AND d.doc_date >= ?"
        params_buy.append(date_from)
        params_sell.append(date_from)
    if date_to:
        date_filter += " AND d.doc_date <= ?"
        params_buy.append(date_to)
        params_sell.append(date_to)

    rows = conn.execute(f"""
        SELECT p.id, p.name, p.unit,
            COALESCE(
                (SELECT SUM(di.quantity) FROM document_items di
                 JOIN documents d ON di.document_id = d.id
                 WHERE di.product_id = p.id AND d.doc_type = 'buy'{date_filter}), 0
            ) as bought,
            COALESCE(
                (SELECT SUM(di.quantity) FROM document_items di
                 JOIN documents d ON di.document_id = d.id
                 WHERE di.product_id = p.id AND d.doc_type = 'sell'{date_filter}), 0
            ) as sold
        FROM products p
        WHERE p.active = 1
        ORDER BY p.name
    """, params_buy + params_sell).fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "unit": r["unit"],
             "bought": r["bought"], "sold": r["sold"],
             "stock": r["bought"] - r["sold"]} for r in rows]


def get_product_stock(product_id):
    """Get current stock for a single product."""
    conn = get_connection()
    stock = _get_product_stock(conn, product_id)
    conn.close()
    return stock
