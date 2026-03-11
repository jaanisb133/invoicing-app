"""
Database module for V-Rēķini (Web).
Multi-tenant SaaS architecture: all business data is isolated per user.
"""

import sqlite3
import os
import datetime
import secrets

import bcrypt

DB_NAME = "veggie_invoices.db"

_db_dir = os.path.dirname(os.path.abspath(__file__))
_db_path = os.path.join(os.path.dirname(_db_dir), "data", DB_NAME)


def get_db_path():
    data_dir = os.path.dirname(_db_path)
    os.makedirs(data_dir, exist_ok=True)
    return _db_path


def get_connection():
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database schema with multi-tenant support."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL DEFAULT '',
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            must_change_password INTEGER NOT NULL DEFAULT 0,
            is_admin INTEGER NOT NULL DEFAULT 0,
            tier TEXT NOT NULL DEFAULT 'free',
            subscription_status TEXT NOT NULL DEFAULT 'active',
            subscription_start DATE,
            subscription_end DATE,
            max_documents INTEGER NOT NULL DEFAULT 50,
            max_clients INTEGER NOT NULL DEFAULT 20,
            max_products INTEGER NOT NULL DEFAULT 50,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, key)
        );

        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            unit TEXT NOT NULL DEFAULT 'kg',
            active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            doc_type TEXT NOT NULL CHECK(doc_type IN ('buy', 'sell')),
            doc_number TEXT NOT NULL,
            seq_num INTEGER NOT NULL DEFAULT 0,
            client_id INTEGER NOT NULL,
            doc_date DATE NOT NULL,
            vat_rate REAL NOT NULL DEFAULT 21.0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
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
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            prefix TEXT NOT NULL,
            last_number INTEGER NOT NULL DEFAULT 0,
            year INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, prefix, year)
        );

        CREATE TABLE IF NOT EXISTS recycled_numbers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            doc_type TEXT NOT NULL,
            year INTEGER NOT NULL,
            number INTEGER NOT NULL,
            recycled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS recurring_invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            doc_type TEXT NOT NULL DEFAULT 'sell',
            client_id INTEGER NOT NULL,
            vat_rate REAL NOT NULL DEFAULT 21.0,
            notes TEXT DEFAULT '',
            template TEXT DEFAULT 'classic',
            frequency TEXT NOT NULL DEFAULT 'monthly',
            next_run DATE NOT NULL,
            send_email INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            items_json TEXT NOT NULL DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        );
    """)

    conn.commit()
    conn.close()
    _run_migrations()


def _run_migrations():
    """Add columns to existing tables if they don't exist yet."""
    conn = get_connection()
    cursor = conn.cursor()

    # Check users table columns
    cols = {row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()}
    migrations = {
        "email": "ALTER TABLE users ADD COLUMN email TEXT NOT NULL DEFAULT ''",
        "tier": "ALTER TABLE users ADD COLUMN tier TEXT NOT NULL DEFAULT 'free'",
        "subscription_status": "ALTER TABLE users ADD COLUMN subscription_status TEXT NOT NULL DEFAULT 'active'",
        "subscription_start": "ALTER TABLE users ADD COLUMN subscription_start DATE",
        "subscription_end": "ALTER TABLE users ADD COLUMN subscription_end DATE",
        "max_documents": "ALTER TABLE users ADD COLUMN max_documents INTEGER NOT NULL DEFAULT 50",
        "max_clients": "ALTER TABLE users ADD COLUMN max_clients INTEGER NOT NULL DEFAULT 20",
        "max_products": "ALTER TABLE users ADD COLUMN max_products INTEGER NOT NULL DEFAULT 50",
    }
    for col, sql in migrations.items():
        if col not in cols:
            cursor.execute(sql)

    # Check if user_id exists in business tables, add if not
    for table in ["products", "clients", "documents", "doc_sequences", "recycled_numbers"]:
        table_cols = {row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()}
        if "user_id" not in table_cols:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0")

    # Add seq_num column to documents if missing
    doc_cols = {row[1] for row in cursor.execute("PRAGMA table_info(documents)").fetchall()}
    if "seq_num" not in doc_cols:
        cursor.execute("ALTER TABLE documents ADD COLUMN seq_num INTEGER NOT NULL DEFAULT 0")
    if "status" not in doc_cols:
        cursor.execute("ALTER TABLE documents ADD COLUMN status TEXT NOT NULL DEFAULT 'issued'")

    # Create user_settings table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, key)
        )
    """)

    conn.commit()
    conn.close()


# --- Global Settings (system-level) ---

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


# --- Per-User Settings ---

def get_user_setting(user_id, key, default=""):
    conn = get_connection()
    row = conn.execute(
        "SELECT value FROM user_settings WHERE user_id = ? AND key = ?",
        (user_id, key)
    ).fetchone()
    conn.close()
    return row["value"] if row else default


def set_user_setting(user_id, key, value):
    conn = get_connection()
    conn.execute(
        "INSERT INTO user_settings (user_id, key, value) VALUES (?, ?, ?) "
        "ON CONFLICT(user_id, key) DO UPDATE SET value = ?",
        (user_id, key, value, value)
    )
    conn.commit()
    conn.close()


def get_all_user_settings(user_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT key, value FROM user_settings WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}


def save_all_user_settings(user_id, settings_dict):
    conn = get_connection()
    for key, value in settings_dict.items():
        conn.execute(
            "INSERT INTO user_settings (user_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, key) DO UPDATE SET value = ?",
            (user_id, key, value, value)
        )
    conn.commit()
    conn.close()


# Legacy compatibility
def get_all_settings():
    conn = get_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}


def save_all_settings(settings_dict):
    conn = get_connection()
    for key, value in settings_dict.items():
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?",
            (key, value, value)
        )
    conn.commit()
    conn.close()


# --- Products (per-user) ---

def add_product(user_id, name, unit):
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO products (user_id, name, unit) VALUES (?, ?, ?)",
        (user_id, name, unit)
    )
    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return product_id


def update_product(user_id, product_id, name, unit):
    conn = get_connection()
    conn.execute(
        "UPDATE products SET name = ?, unit = ? WHERE id = ? AND user_id = ?",
        (name, unit, product_id, user_id)
    )
    conn.commit()
    conn.close()


def delete_product(user_id, product_id):
    conn = get_connection()
    conn.execute("UPDATE products SET active = 0 WHERE id = ? AND user_id = ?",
                 (product_id, user_id))
    conn.commit()
    conn.close()


def get_all_products(user_id, active_only=True):
    conn = get_connection()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM products WHERE user_id = ? AND active = 1 ORDER BY name",
            (user_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM products WHERE user_id = ? ORDER BY name",
            (user_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product(product_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# --- Clients (per-user) ---

def add_client(user_id, name, reg_number="", vat_number="", legal_address="",
               bank_name="", bank_account="", contact_person="", phone="", email=""):
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO clients (user_id, name, reg_number, vat_number, legal_address,
           bank_name, bank_account, contact_person, phone, email)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, name, reg_number, vat_number, legal_address,
         bank_name, bank_account, contact_person, phone, email)
    )
    client_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return client_id


def update_client(user_id, client_id, **kwargs):
    allowed_fields = {"name", "reg_number", "vat_number", "legal_address",
                      "bank_name", "bank_account", "contact_person", "phone", "email"}
    conn = get_connection()
    for key, value in kwargs.items():
        if key in allowed_fields:
            conn.execute(f"UPDATE clients SET {key} = ? WHERE id = ? AND user_id = ?",
                         (value, client_id, user_id))
    conn.commit()
    conn.close()


def delete_client(user_id, client_id):
    conn = get_connection()
    conn.execute("UPDATE clients SET active = 0 WHERE id = ? AND user_id = ?",
                 (client_id, user_id))
    conn.commit()
    conn.close()


def get_all_clients(user_id, active_only=True):
    conn = get_connection()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM clients WHERE user_id = ? AND active = 1 ORDER BY name",
            (user_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM clients WHERE user_id = ? ORDER BY name",
            (user_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_client(client_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# --- Documents (per-user) ---

def get_next_doc_number(user_id, doc_type, doc_date, conn=None):
    """
    Get next document number based on user's invoice_number_type setting.

    Types:
    - type1: YEAR + sequential (e.g., 26-001, 26-002)
    - type2: SEQ/DAY-MONTH, resets daily (e.g., 01/09-03)
    - type3: Simple sequential (e.g., 001, 002)
    """
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True

    # Get user's numbering settings
    settings = {}
    rows = conn.execute(
        "SELECT key, value FROM user_settings WHERE user_id = ?", (user_id,)
    ).fetchall()
    for r in rows:
        settings[r["key"]] = r["value"]

    number_type = settings.get("invoice_number_type", "type1")
    separator = settings.get("invoice_number_separator", "-")
    min_digits = int(settings.get("invoice_number_digits", "3"))
    prefix = settings.get("sell_doc_prefix", "PAR") if doc_type == "sell" else settings.get("buy_doc_prefix", "PIR")

    if isinstance(doc_date, str):
        doc_date_obj = datetime.date.fromisoformat(doc_date)
    else:
        doc_date_obj = doc_date

    year = doc_date_obj.year
    year_short = year % 100

    if number_type == "type2":
        # Type 2: SEQ/DAY-MONTH, resets daily
        day = doc_date_obj.day
        month = doc_date_obj.month
        date_str = doc_date_obj.isoformat()

        # Count documents already created for this date
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM documents WHERE user_id = ? AND doc_type = ? AND doc_date = ?",
            (user_id, doc_type, date_str)
        ).fetchone()
        next_num = (row["cnt"] if row else 0) + 1

        doc_number = f"{next_num:02d}/{day:02d}-{month:02d}"
        if prefix:
            doc_number = f"{prefix}-{doc_number}"

        if close_conn:
            conn.commit()
            conn.close()
        return doc_number, next_num

    elif number_type == "type3":
        # Type 3: Simple sequential from 001
        # Use MAX(seq_num) from existing documents so deletions naturally reset the counter
        row = conn.execute(
            "SELECT MAX(seq_num) as max_num FROM documents WHERE user_id = ? AND doc_type = ?",
            (user_id, doc_type)
        ).fetchone()
        next_num = (row["max_num"] or 0) + 1

        doc_number = str(next_num).zfill(min_digits)
        if prefix:
            doc_number = f"{prefix}-{doc_number}"

        if close_conn:
            conn.commit()
            conn.close()
        return doc_number, next_num

    else:
        # Type 1 (default): YEAR + sequential (e.g., 26-001)
        # Use MAX(seq_num) from existing documents for this year so deletions naturally reset
        row = conn.execute(
            "SELECT MAX(seq_num) as max_num FROM documents WHERE user_id = ? AND doc_type = ? AND strftime('%Y', doc_date) = ?",
            (user_id, doc_type, str(year))
        ).fetchone()
        next_num = (row["max_num"] or 0) + 1

        num_str = str(next_num).zfill(min_digits)
        doc_number = f"{year_short}{separator}{num_str}"
        if prefix:
            doc_number = f"{prefix}-{doc_number}"

        if close_conn:
            conn.commit()
            conn.close()
        return doc_number, next_num


def create_document(user_id, doc_type, client_id, doc_date, items, vat_rate=21.0, notes=""):
    """
    Create a document with line items.
    items: list of dicts with keys: product_id, quantity, unit, price_per_unit
    Returns (document_id, doc_number) or raises ValueError.
    """
    conn = get_connection()
    try:
        stock_on = get_user_setting(user_id, "stock_enabled", "0") == "1"
        if stock_on and doc_type == "sell":
            for item in items:
                available = _get_product_stock(conn, item["product_id"], user_id)
                product = get_product(item["product_id"])
                if item["quantity"] > available:
                    product_name = product["name"] if product else f"ID:{item['product_id']}"
                    raise ValueError(
                        f"Nepietiekams daudzums: {product_name}. "
                        f"Pieejams: {available:.2f}, pieprasīts: {item['quantity']:.2f}"
                    )

        doc_number, seq_num = get_next_doc_number(user_id, doc_type, doc_date, conn)

        cursor = conn.execute(
            """INSERT INTO documents (user_id, doc_type, doc_number, seq_num, client_id, doc_date, vat_rate, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, doc_type, doc_number, seq_num, client_id,
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


def update_document(user_id, doc_id, client_id, doc_date, items, vat_rate=21.0, notes=""):
    """
    Update an existing document and its line items.
    items: list of dicts with keys: product_id, quantity, unit, price_per_unit
    """
    conn = get_connection()
    try:
        # Verify ownership
        doc = conn.execute(
            "SELECT * FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id)
        ).fetchone()
        if not doc:
            raise ValueError("Dokuments nav atrasts")

        stock_on = get_user_setting(user_id, "stock_enabled", "0") == "1"
        if stock_on and doc["doc_type"] == "sell":
            for item in items:
                # Get current stock, but add back what this document previously sold
                available = _get_product_stock(conn, item["product_id"], user_id)
                # Add back quantities from existing document items for this product
                existing = conn.execute(
                    "SELECT COALESCE(SUM(quantity), 0) as qty FROM document_items "
                    "WHERE document_id = ? AND product_id = ?",
                    (doc_id, item["product_id"])
                ).fetchone()
                available += existing["qty"]
                product = get_product(item["product_id"])
                if item["quantity"] > available:
                    product_name = product["name"] if product else f"ID:{item['product_id']}"
                    raise ValueError(
                        f"Nepietiekams daudzums: {product_name}. "
                        f"Pieejams: {available:.2f}, pieprasīts: {item['quantity']:.2f}"
                    )

        # Update document fields
        conn.execute(
            """UPDATE documents SET client_id = ?, doc_date = ?, vat_rate = ?, notes = ?
               WHERE id = ? AND user_id = ?""",
            (client_id, doc_date if isinstance(doc_date, str) else doc_date.isoformat(),
             vat_rate, notes, doc_id, user_id)
        )

        # Delete old items and insert new ones
        conn.execute("DELETE FROM document_items WHERE document_id = ?", (doc_id,))
        for item in items:
            total = item["quantity"] * item["price_per_unit"]
            conn.execute(
                """INSERT INTO document_items (document_id, product_id, quantity, unit, price_per_unit, total)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (doc_id, item["product_id"], item["quantity"], item["unit"],
                 item["price_per_unit"], total)
            )

        conn.commit()
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


def get_documents(user_id, doc_type=None, client_id=None, date_from=None, date_to=None):
    conn = get_connection()
    query = """SELECT d.*, c.name as client_name
               FROM documents d
               JOIN clients c ON d.client_id = c.id
               WHERE d.user_id = ?"""
    params = [user_id]

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


def update_document_status(user_id, doc_id, status):
    conn = get_connection()
    conn.execute("UPDATE documents SET status = ? WHERE id = ? AND user_id = ?",
                 (status, doc_id, user_id))
    conn.commit()
    conn.close()


def delete_document(user_id, doc_id):
    conn = get_connection()
    conn.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
    conn.commit()
    conn.close()


# --- Stock (per-user) ---

def _get_product_stock(conn, product_id, user_id):
    # Only count documents created after stock was enabled
    enabled_date = ""
    row_s = conn.execute(
        "SELECT value FROM user_settings WHERE user_id = ? AND key = 'stock_enabled_date'",
        (user_id,)
    ).fetchone()
    if row_s:
        enabled_date = row_s["value"]

    date_filter = ""
    params_buy = [product_id, user_id]
    params_sell = [product_id, user_id]
    if enabled_date:
        date_filter = " AND d.created_at >= ?"
        params_buy.append(enabled_date)
        params_sell.append(enabled_date)

    row = conn.execute(f"""
        SELECT
            COALESCE(
                (SELECT SUM(di.quantity) FROM document_items di
                 JOIN documents d ON di.document_id = d.id
                 WHERE di.product_id = ? AND d.doc_type = 'buy' AND d.user_id = ?{date_filter}), 0
            ) -
            COALESCE(
                (SELECT SUM(di.quantity) FROM document_items di
                 JOIN documents d ON di.document_id = d.id
                 WHERE di.product_id = ? AND d.doc_type = 'sell' AND d.user_id = ?{date_filter}), 0
            ) as stock
    """, params_buy + params_sell).fetchone()
    return row["stock"] if row else 0


def get_stock(user_id, date_from=None, date_to=None):
    conn = get_connection()

    # Respect stock_enabled_date: only count documents created on or after that date
    enabled_row = conn.execute(
        "SELECT value FROM user_settings WHERE user_id = ? AND key = 'stock_enabled_date'",
        (user_id,)
    ).fetchone()
    enabled_date = enabled_row["value"] if enabled_row and enabled_row["value"] else None

    date_filter = ""
    params_buy = [user_id]
    params_sell = [user_id]

    if enabled_date:
        date_filter += " AND d.created_at >= ?"
        params_buy.append(enabled_date)
        params_sell.append(enabled_date)

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
                 WHERE di.product_id = p.id AND d.doc_type = 'buy' AND d.user_id = ?{date_filter}), 0
            ) as bought,
            COALESCE(
                (SELECT SUM(di.quantity) FROM document_items di
                 JOIN documents d ON di.document_id = d.id
                 WHERE di.product_id = p.id AND d.doc_type = 'sell' AND d.user_id = ?{date_filter}), 0
            ) as sold
        FROM products p
        WHERE p.user_id = ? AND p.active = 1
        ORDER BY p.name
    """, params_buy + params_sell + [user_id]).fetchall()
    conn.close()
    return [{"id": r["id"], "name": r["name"], "unit": r["unit"],
             "bought": r["bought"], "sold": r["sold"],
             "stock": r["bought"] - r["sold"]} for r in rows]


def get_product_stock(user_id, product_id):
    conn = get_connection()
    stock = _get_product_stock(conn, product_id, user_id)
    conn.close()
    return stock


# --- Users / Auth ---

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _check_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_user(username: str, password: str, display_name: str = "",
                email: str = "", is_admin: bool = False,
                must_change_password: bool = False,
                tier: str = "free") -> int:
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO users (username, email, password_hash, display_name,
           is_admin, must_change_password, tier, subscription_status, subscription_start)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
        (username.lower().strip(), email.strip(), _hash_password(password),
         display_name, 1 if is_admin else 0, 1 if must_change_password else 0,
         tier, datetime.date.today().isoformat())
    )
    user_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return user_id


def authenticate_user(username: str, password: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?",
                       (username.lower().strip(),)).fetchone()
    conn.close()
    if row and _check_password(password, row["password_hash"]):
        return dict(row)
    return None


def get_user(user_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_username(username: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE username = ?",
                       (username.lower().strip(),)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_email(email: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE email = ?",
                       (email.strip().lower(),)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users():
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username, email, display_name, is_admin, tier, subscription_status, created_at "
        "FROM users ORDER BY username"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_user_password(user_id: int, new_password: str):
    conn = get_connection()
    conn.execute("UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
                 (_hash_password(new_password), user_id))
    conn.commit()
    conn.close()


def update_user_profile(user_id: int, display_name: str = None, email: str = None):
    conn = get_connection()
    if display_name is not None:
        conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name, user_id))
    if email is not None:
        conn.execute("UPDATE users SET email = ? WHERE id = ?", (email.strip(), user_id))
    conn.commit()
    conn.close()


def delete_user(user_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()


def user_count() -> int:
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
    conn.close()
    return row["cnt"]


def get_dashboard_stats(user_id: int) -> dict:
    """Get dashboard statistics for a user."""
    conn = get_connection()
    today = datetime.date.today()
    week_ago = (today - datetime.timedelta(days=7)).isoformat()
    today_str = today.isoformat()

    # Invoices in last 7 days
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM documents WHERE user_id = ? AND doc_date >= ?",
        (user_id, week_ago)
    ).fetchone()
    docs_last_7_days = row["cnt"] if row else 0

    # Total revenue (sum of sell document totals)
    row = conn.execute("""
        SELECT COALESCE(SUM(di.quantity * di.price_per_unit * (1 + d.vat_rate / 100)), 0) as total
        FROM documents d
        JOIN document_items di ON di.document_id = d.id
        WHERE d.user_id = ? AND d.doc_type = 'sell'
    """, (user_id,)).fetchone()
    total_revenue = row["total"] if row else 0

    # Revenue last 7 days
    row = conn.execute("""
        SELECT COALESCE(SUM(di.quantity * di.price_per_unit * (1 + d.vat_rate / 100)), 0) as total
        FROM documents d
        JOIN document_items di ON di.document_id = d.id
        WHERE d.user_id = ? AND d.doc_type = 'sell' AND d.doc_date >= ?
    """, (user_id, week_ago)).fetchone()
    revenue_last_7_days = row["total"] if row else 0

    # Most used client (by document count)
    row = conn.execute("""
        SELECT c.name, COUNT(*) as cnt
        FROM documents d
        JOIN clients c ON d.client_id = c.id
        WHERE d.user_id = ?
        GROUP BY d.client_id
        ORDER BY cnt DESC
        LIMIT 1
    """, (user_id,)).fetchone()
    top_client = {"name": row["name"], "count": row["cnt"]} if row else None

    # Most sold product/service (by total quantity in sell documents)
    row = conn.execute("""
        SELECT p.name, SUM(di.quantity) as total_qty, p.unit
        FROM document_items di
        JOIN documents d ON di.document_id = d.id
        JOIN products p ON di.product_id = p.id
        WHERE d.user_id = ? AND d.doc_type = 'sell'
        GROUP BY di.product_id
        ORDER BY total_qty DESC
        LIMIT 1
    """, (user_id,)).fetchone()
    top_product = {"name": row["name"], "quantity": row["total_qty"], "unit": row["unit"]} if row else None

    # Total documents
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM documents WHERE user_id = ?", (user_id,)
    ).fetchone()
    total_docs = row["cnt"] if row else 0

    conn.close()
    return {
        "docs_last_7_days": docs_last_7_days,
        "total_revenue": total_revenue,
        "revenue_last_7_days": revenue_last_7_days,
        "top_client": top_client,
        "top_product": top_product,
        "total_docs": total_docs,
    }


def get_user_document_count(user_id: int) -> int:
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as cnt FROM documents WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["cnt"]


def ensure_default_admin():
    """Create default admin account if no users exist."""
    if user_count() == 0:
        temp_password = secrets.token_urlsafe(12)
        create_user(
            username="admin",
            password=temp_password,
            display_name="Administrators",
            is_admin=True,
            must_change_password=True,
            tier="admin",
        )
        return temp_password
    return None


# --- Tier limits ---

TIER_LIMITS = {
    "free": {"max_documents": 50, "max_clients": 20, "max_products": 50, "label": "Bezmaksas"},
    "starter": {"max_documents": 500, "max_clients": 100, "max_products": 200, "label": "Sākums"},
    "business": {"max_documents": 5000, "max_clients": 500, "max_products": 1000, "label": "Bizness"},
    "admin": {"max_documents": 999999, "max_clients": 999999, "max_products": 999999, "label": "Administrators"},
}


def get_tier_limits(tier):
    return TIER_LIMITS.get(tier, TIER_LIMITS["free"])


# --- Recurring Invoices ---

def create_recurring_invoice(user_id, doc_type, client_id, vat_rate, notes, template,
                             frequency, next_run, send_email, items_json):
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO recurring_invoices
           (user_id, doc_type, client_id, vat_rate, notes, template, frequency, next_run, send_email, items_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, doc_type, client_id, vat_rate, notes, template, frequency, next_run,
         1 if send_email else 0, items_json)
    )
    rid = cursor.lastrowid
    conn.commit()
    conn.close()
    return rid


def get_recurring_invoices(user_id):
    conn = get_connection()
    rows = conn.execute(
        """SELECT r.*, c.name as client_name FROM recurring_invoices r
           JOIN clients c ON r.client_id = c.id
           WHERE r.user_id = ? ORDER BY r.next_run""",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recurring_invoice(recurring_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM recurring_invoices WHERE id = ?", (recurring_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_recurring_next_run(recurring_id, next_run):
    conn = get_connection()
    conn.execute("UPDATE recurring_invoices SET next_run = ? WHERE id = ?", (next_run, recurring_id))
    conn.commit()
    conn.close()


def delete_recurring_invoice(user_id, recurring_id):
    conn = get_connection()
    conn.execute("DELETE FROM recurring_invoices WHERE id = ? AND user_id = ?", (recurring_id, user_id))
    conn.commit()
    conn.close()


def toggle_recurring_invoice(user_id, recurring_id):
    conn = get_connection()
    conn.execute(
        "UPDATE recurring_invoices SET active = CASE WHEN active = 1 THEN 0 ELSE 1 END WHERE id = ? AND user_id = ?",
        (recurring_id, user_id)
    )
    conn.commit()
    conn.close()


def get_due_recurring_invoices(today_str):
    """Get all active recurring invoices due on or before today."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM recurring_invoices WHERE active = 1 AND next_run <= ?",
        (today_str,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
