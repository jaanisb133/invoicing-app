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
_default_db_path = os.path.join(os.path.dirname(_db_dir), "data", DB_NAME)

# Allow overriding via environment variable for production reliability
_db_path = os.environ.get("VREKINI_DB_PATH", _default_db_path)


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
            billing_cycle TEXT NOT NULL DEFAULT '',
            everypay_token TEXT NOT NULL DEFAULT '',
            everypay_payment_ref TEXT NOT NULL DEFAULT '',
            phone TEXT NOT NULL DEFAULT '',
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
            unit TEXT NOT NULL DEFAULT 'gab',
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
            vat_payer INTEGER NOT NULL DEFAULT 0,
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
            doc_type TEXT NOT NULL,
            doc_number TEXT NOT NULL,
            seq_num INTEGER NOT NULL DEFAULT 0,
            client_id INTEGER NOT NULL,
            doc_date DATE NOT NULL,
            payment_due_date DATE,
            vat_rate REAL NOT NULL DEFAULT 21.0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        );

        CREATE TABLE IF NOT EXISTS document_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            product_id INTEGER,
            description TEXT DEFAULT '',
            quantity REAL NOT NULL,
            unit TEXT NOT NULL,
            price_per_unit REAL NOT NULL,
            total REAL NOT NULL,
            included_in_price INTEGER NOT NULL DEFAULT 0,
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
            template TEXT DEFAULT 'minimal',
            frequency TEXT NOT NULL DEFAULT 'monthly',
            next_run DATE NOT NULL,
            send_email INTEGER NOT NULL DEFAULT 0,
            email_subject TEXT NOT NULL DEFAULT '',
            email_body TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            items_json TEXT NOT NULL DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        );

        CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            document_id INTEGER,
            recipient TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'manual',
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            document_id INTEGER,
            client_id INTEGER,
            meta TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_events_user_created ON events(user_id, created_at DESC);
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
        "billing_cycle": "ALTER TABLE users ADD COLUMN billing_cycle TEXT NOT NULL DEFAULT ''",
        "everypay_token": "ALTER TABLE users ADD COLUMN everypay_token TEXT NOT NULL DEFAULT ''",
        "everypay_payment_ref": "ALTER TABLE users ADD COLUMN everypay_payment_ref TEXT NOT NULL DEFAULT ''",
        "phone": "ALTER TABLE users ADD COLUMN phone TEXT NOT NULL DEFAULT ''",
        "renewal_attempts": "ALTER TABLE users ADD COLUMN renewal_attempts INTEGER NOT NULL DEFAULT 0",
        "last_renewal_attempt": "ALTER TABLE users ADD COLUMN last_renewal_attempt TIMESTAMP",
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
    if "payment_due_date" not in doc_cols:
        cursor.execute("ALTER TABLE documents ADD COLUMN payment_due_date DATE")
    if "reverse_charge" not in doc_cols:
        cursor.execute("ALTER TABLE documents ADD COLUMN reverse_charge INTEGER NOT NULL DEFAULT 0")
    if "deleted_at" not in doc_cols:
        cursor.execute("ALTER TABLE documents ADD COLUMN deleted_at TIMESTAMP")

    # Add vat_payer column to clients if missing
    client_cols = {row[1] for row in cursor.execute("PRAGMA table_info(clients)").fetchall()}
    if "vat_payer" not in client_cols:
        cursor.execute("ALTER TABLE clients ADD COLUMN vat_payer INTEGER NOT NULL DEFAULT 0")
    if "client_type" not in client_cols:
        cursor.execute("ALTER TABLE clients ADD COLUMN client_type TEXT NOT NULL DEFAULT 'business'")
    if "one_time" not in client_cols:
        cursor.execute("ALTER TABLE clients ADD COLUMN one_time INTEGER NOT NULL DEFAULT 0")

    # Add email_subject / email_body to recurring_invoices if missing
    rec_cols = {row[1] for row in cursor.execute("PRAGMA table_info(recurring_invoices)").fetchall()}
    if "email_subject" not in rec_cols:
        cursor.execute("ALTER TABLE recurring_invoices ADD COLUMN email_subject TEXT NOT NULL DEFAULT ''")
    if "email_body" not in rec_cols:
        cursor.execute("ALTER TABLE recurring_invoices ADD COLUMN email_body TEXT NOT NULL DEFAULT ''")

    # Add source column to email_log if missing
    email_cols = {row[1] for row in cursor.execute("PRAGMA table_info(email_log)").fetchall()}
    if "source" not in email_cols:
        cursor.execute("ALTER TABLE email_log ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'")

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

    # Indexes for common queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_user_monthly ON documents(user_id, deleted_at, created_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_documents_dashboard ON documents(user_id, deleted_at, doc_type, doc_date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_document_items_doc ON document_items(document_id)")

    # Migration: drop the CHECK(doc_type IN ('buy','sell')) constraint so offers
    # (doc_type='offer') can be inserted alongside invoices.
    doc_sql_row = cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='documents'"
    ).fetchone()
    doc_sql = (doc_sql_row[0] if doc_sql_row else "") or ""
    if "CHECK" in doc_sql and "doc_type" in doc_sql:
        cursor.executescript("""
            PRAGMA foreign_keys=OFF;
            CREATE TABLE documents_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                doc_type TEXT NOT NULL,
                doc_number TEXT NOT NULL,
                seq_num INTEGER NOT NULL DEFAULT 0,
                client_id INTEGER NOT NULL,
                doc_date DATE NOT NULL,
                payment_due_date DATE,
                vat_rate REAL NOT NULL DEFAULT 21.0,
                notes TEXT,
                status TEXT NOT NULL DEFAULT 'issued',
                reverse_charge INTEGER NOT NULL DEFAULT 0,
                deleted_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (client_id) REFERENCES clients(id)
            );
            INSERT INTO documents_new (id, user_id, doc_type, doc_number, seq_num,
                                       client_id, doc_date, payment_due_date, vat_rate,
                                       notes, status, reverse_charge, deleted_at, created_at)
                SELECT id, user_id, doc_type, doc_number, seq_num,
                       client_id, doc_date, payment_due_date, vat_rate,
                       notes, status, reverse_charge, deleted_at, created_at
                FROM documents;
            DROP TABLE documents;
            ALTER TABLE documents_new RENAME TO documents;
            CREATE INDEX IF NOT EXISTS idx_documents_user_monthly ON documents(user_id, deleted_at, created_at);
            CREATE INDEX IF NOT EXISTS idx_documents_dashboard ON documents(user_id, deleted_at, doc_type, doc_date);
            PRAGMA foreign_keys=ON;
        """)

    # Migration: allow nullable product_id and add description column on document_items
    item_info = list(cursor.execute("PRAGMA table_info(document_items)").fetchall())
    item_cols = {row[1] for row in item_info}
    product_id_notnull = any(row[1] == 'product_id' and row[3] == 1 for row in item_info)
    if product_id_notnull or "description" not in item_cols:
        cursor.executescript("""
            PRAGMA foreign_keys=OFF;
            CREATE TABLE document_items_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id INTEGER NOT NULL,
                product_id INTEGER,
                description TEXT DEFAULT '',
                quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                price_per_unit REAL NOT NULL,
                total REAL NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
            INSERT INTO document_items_new (id, document_id, product_id, description, quantity, unit, price_per_unit, total)
                SELECT id, document_id, product_id, '', quantity, unit, price_per_unit, total FROM document_items;
            DROP TABLE document_items;
            ALTER TABLE document_items_new RENAME TO document_items;
            CREATE INDEX IF NOT EXISTS idx_document_items_doc ON document_items(document_id);
            PRAGMA foreign_keys=ON;
        """)
        item_cols = {row[1] for row in cursor.execute("PRAGMA table_info(document_items)").fetchall()}

    # Migration: add included_in_price flag used by offer line items
    if "included_in_price" not in item_cols:
        cursor.execute("ALTER TABLE document_items ADD COLUMN included_in_price INTEGER NOT NULL DEFAULT 0")

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


def next_payment_counter():
    """Return the next sequential payment number (global, across all users)."""
    conn = get_connection()
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'payment_counter'"
    ).fetchone()
    counter = int(row["value"]) + 1 if row else 1
    conn.execute(
        "INSERT INTO settings (key, value) VALUES ('payment_counter', ?) "
        "ON CONFLICT(key) DO UPDATE SET value = ?",
        (str(counter), str(counter))
    )
    conn.commit()
    conn.close()
    return counter


def find_user_by_pending_order_ref(order_ref):
    """Find user_id, tier, cycle from a pending order reference stored in user_settings."""
    conn = get_connection()
    row = conn.execute(
        "SELECT user_id FROM user_settings WHERE key = '_pending_order_ref' AND value = ?",
        (order_ref,)
    ).fetchone()
    if not row:
        conn.close()
        return None
    user_id = row["user_id"]
    settings = {r["key"]: r["value"] for r in conn.execute(
        "SELECT key, value FROM user_settings WHERE user_id = ? AND key IN ('_pending_tier', '_pending_cycle')",
        (user_id,)
    ).fetchall()}
    conn.close()
    return {"user_id": user_id, "tier": settings.get("_pending_tier", ""), "cycle": settings.get("_pending_cycle", "")}


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

def add_client(user_id, name, reg_number="", vat_number="", vat_payer=0, legal_address="",
               bank_name="", bank_account="", contact_person="", phone="", email="",
               client_type="business", one_time=0):
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO clients (user_id, name, reg_number, vat_number, vat_payer, legal_address,
           bank_name, bank_account, contact_person, phone, email, client_type, one_time)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, name, reg_number, vat_number, int(vat_payer), legal_address,
         bank_name, bank_account, contact_person, phone, email, client_type, int(one_time))
    )
    client_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return client_id


def update_client(user_id, client_id, **kwargs):
    allowed_fields = {"name", "reg_number", "vat_number", "vat_payer", "legal_address",
                      "bank_name", "bank_account", "contact_person", "phone", "email",
                      "client_type"}
    conn = get_connection()
    for key, value in kwargs.items():
        if key in allowed_fields:
            if key == "vat_payer":
                value = int(value)
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
    """Return the user's saved clients. One-time clients (one_time=1) are
    always excluded — they exist only to attach to a single document and
    should never appear in pickers or the clients page."""
    conn = get_connection()
    if active_only:
        rows = conn.execute(
            "SELECT * FROM clients WHERE user_id = ? AND active = 1 AND one_time = 0 ORDER BY name",
            (user_id,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM clients WHERE user_id = ? AND one_time = 0 ORDER BY name",
            (user_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_client_by_reg_number(user_id, reg_number):
    """Look up an existing saved client by reg number. One-time clients are
    not considered — duplicates are fine when both are one-time."""
    if not reg_number:
        return None
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM clients WHERE user_id = ? AND reg_number = ? AND one_time = 0",
        (user_id, reg_number)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


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
    try:
        start_num = max(1, int(settings.get("invoice_number_start", "1") or "1"))
    except (TypeError, ValueError):
        start_num = 1
    if doc_type == "offer":
        # Offers always use their own prefix (default "P") and their own counter,
        # independent of the user's prefix toggle for invoices.
        prefix = settings.get("offer_doc_prefix", "P")
    elif settings.get("use_prefixes", "0") == "1":
        prefix = settings.get("sell_doc_prefix", "") if doc_type == "sell" else settings.get("buy_doc_prefix", "")
    else:
        prefix = ""

    # Offers get a sequence scoped to doc_type='offer' so their numbering is
    # independent of invoices.
    offer_scope = " AND doc_type='offer'" if doc_type == "offer" else " AND doc_type!='offer'"

    if isinstance(doc_date, str):
        doc_date_obj = datetime.date.fromisoformat(doc_date)
    else:
        doc_date_obj = doc_date

    year = doc_date_obj.year
    year_short = year % 100

    if number_type == "type2":
        # Type 2: SEQ/DAY-MONTH, resets daily. Trashed docs (deleted_at IS NOT NULL)
        # free up their slot so the next invoice can reuse the number.
        day = doc_date_obj.day
        month = doc_date_obj.month
        date_str = doc_date_obj.isoformat()

        row = conn.execute(
            f"SELECT COUNT(*) as cnt FROM documents WHERE user_id = ? AND doc_date = ? AND deleted_at IS NULL{offer_scope}",
            (user_id, date_str)
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
        # Type 3: Simple sequential. Excludes trashed docs so deletion frees the number.
        row = conn.execute(
            f"SELECT MAX(seq_num) as max_num FROM documents WHERE user_id = ? AND deleted_at IS NULL{offer_scope}",
            (user_id,)
        ).fetchone()
        max_existing = row["max_num"] or 0
        # next = whichever is higher: next after existing, or the user-chosen start
        next_num = max(max_existing + 1, start_num)

        doc_number = str(next_num).zfill(min_digits)
        if prefix:
            doc_number = f"{prefix}-{doc_number}"

        if close_conn:
            conn.commit()
            conn.close()
        return doc_number, next_num

    else:
        # Type 1 (default): YEAR + sequential, starts from invoice_number_start each year.
        # Excludes trashed docs so deletion frees the number.
        row = conn.execute(
            f"SELECT MAX(seq_num) as max_num FROM documents WHERE user_id = ? AND deleted_at IS NULL{offer_scope} AND strftime('%Y', doc_date) = ?",
            (user_id, str(year))
        ).fetchone()
        max_existing = row["max_num"] or 0
        next_num = max(max_existing + 1, start_num)

        num_str = str(next_num).zfill(min_digits)
        doc_number = f"{year_short}{separator}{num_str}"
        if prefix:
            doc_number = f"{prefix}-{doc_number}"

        if close_conn:
            conn.commit()
            conn.close()
        return doc_number, next_num


def create_document(user_id, doc_type, client_id, doc_date, items, vat_rate=21.0, notes="", payment_due_date="", reverse_charge=False):
    """
    Create a document with line items.
    items: list of dicts with keys: product_id (int or None), description (str, used
           when product_id is None), quantity, unit, price_per_unit
    Returns (document_id, doc_number) or raises ValueError.
    """
    conn = get_connection()
    try:
        stock_on = get_user_setting(user_id, "stock_enabled", "0") == "1"
        if stock_on and doc_type == "sell":
            for item in items:
                pid = item.get("product_id")
                if not pid:
                    continue  # Free-text items don't affect stock
                available = _get_product_stock(conn, pid, user_id)
                product = get_product(pid)
                if item["quantity"] > available:
                    product_name = product["name"] if product else f"ID:{pid}"
                    raise ValueError(
                        f"Nepietiekams daudzums: {product_name}. "
                        f"Pieejams: {available:.2f}, pieprasīts: {item['quantity']:.2f}"
                    )

        doc_number, seq_num = get_next_doc_number(user_id, doc_type, doc_date, conn)

        cursor = conn.execute(
            """INSERT INTO documents (user_id, doc_type, doc_number, seq_num, client_id, doc_date, payment_due_date, vat_rate, notes, reverse_charge)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, doc_type, doc_number, seq_num, client_id,
             doc_date if isinstance(doc_date, str) else doc_date.isoformat(),
             payment_due_date or None, vat_rate, notes, int(reverse_charge))
        )
        doc_id = cursor.lastrowid

        for item in items:
            included = 1 if item.get("included_in_price") else 0
            price = 0.0 if included else item["price_per_unit"]
            total = 0.0 if included else item["quantity"] * price
            pid = item.get("product_id") or None
            description = item.get("description", "") or ""
            conn.execute(
                """INSERT INTO document_items (document_id, product_id, description, quantity, unit, price_per_unit, total, included_in_price)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, pid, description, item["quantity"], item["unit"],
                 price, total, included)
            )

        conn.commit()
        return doc_id, doc_number
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def update_document(user_id, doc_id, client_id, doc_date, items, vat_rate=21.0, notes="", payment_due_date="", reverse_charge=False):
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
                pid = item.get("product_id")
                if not pid:
                    continue
                # Get current stock, but add back what this document previously sold
                available = _get_product_stock(conn, pid, user_id)
                existing = conn.execute(
                    "SELECT COALESCE(SUM(quantity), 0) as qty FROM document_items "
                    "WHERE document_id = ? AND product_id = ?",
                    (doc_id, pid)
                ).fetchone()
                available += existing["qty"]
                product = get_product(pid)
                if item["quantity"] > available:
                    product_name = product["name"] if product else f"ID:{pid}"
                    raise ValueError(
                        f"Nepietiekams daudzums: {product_name}. "
                        f"Pieejams: {available:.2f}, pieprasīts: {item['quantity']:.2f}"
                    )

        # Update document fields
        conn.execute(
            """UPDATE documents SET client_id = ?, doc_date = ?, payment_due_date = ?, vat_rate = ?, notes = ?, reverse_charge = ?
               WHERE id = ? AND user_id = ?""",
            (client_id, doc_date if isinstance(doc_date, str) else doc_date.isoformat(),
             payment_due_date or None, vat_rate, notes, int(reverse_charge), doc_id, user_id)
        )

        # Delete old items and insert new ones
        conn.execute("DELETE FROM document_items WHERE document_id = ?", (doc_id,))
        for item in items:
            included = 1 if item.get("included_in_price") else 0
            price = 0.0 if included else item["price_per_unit"]
            total = 0.0 if included else item["quantity"] * price
            pid = item.get("product_id") or None
            description = item.get("description", "") or ""
            conn.execute(
                """INSERT INTO document_items (document_id, product_id, description, quantity, unit, price_per_unit, total, included_in_price)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (doc_id, pid, description, item["quantity"], item["unit"],
                 price, total, included)
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
        """SELECT di.*,
                  COALESCE(p.name, di.description, '') as product_name
           FROM document_items di
           LEFT JOIN products p ON di.product_id = p.id
           WHERE di.document_id = ?""",
        (doc_id,)
    ).fetchall()
    conn.close()
    return (dict(doc) if doc else None, [dict(i) for i in items])


def get_documents(user_id, doc_type=None, client_id=None, date_from=None, date_to=None,
                  status=None, exclude_doc_types=None):
    conn = get_connection()
    query = """SELECT d.*, c.name as client_name,
               ROUND(COALESCE((SELECT SUM(di.total) FROM document_items di WHERE di.document_id = d.id), 0) * (1 + d.vat_rate / 100.0), 2) as total_with_vat
               FROM documents d
               JOIN clients c ON d.client_id = c.id
               WHERE d.user_id = ? AND d.deleted_at IS NULL"""
    params = [user_id]

    if doc_type:
        query += " AND d.doc_type = ?"
        params.append(doc_type)
    if exclude_doc_types:
        placeholders = ",".join(["?"] * len(exclude_doc_types))
        query += f" AND d.doc_type NOT IN ({placeholders})"
        params.extend(exclude_doc_types)
    if client_id:
        query += " AND d.client_id = ?"
        params.append(client_id)
    if date_from:
        query += " AND d.doc_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND d.doc_date <= ?"
        params.append(date_to)
    if status:
        query += " AND d.status = ?"
        params.append(status)

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
    """Soft-delete a document (move to trash). Permanently deleted after 7 days."""
    conn = get_connection()
    conn.execute(
        "UPDATE documents SET deleted_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
        (doc_id, user_id)
    )
    conn.commit()
    conn.close()


def restore_document(user_id, doc_id):
    """Restore a soft-deleted document from trash.

    If the doc's seq_num was reused while it was trashed, allocate a fresh
    number (and update the doc_number string) before un-trashing so we never
    leave two active docs with the same number.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, doc_type, doc_number, seq_num, doc_date FROM documents WHERE id = ? AND user_id = ?",
            (doc_id, user_id)
        ).fetchone()
        if not row:
            return False

        # Is the seq_num occupied by another active doc in the same scope?
        year = row["doc_date"][:4] if row["doc_date"] else None
        collision = conn.execute(
            """SELECT 1 FROM documents
               WHERE user_id = ? AND id != ? AND deleted_at IS NULL
                 AND seq_num = ?
                 AND (? IS NULL OR strftime('%Y', doc_date) = ?)""",
            (user_id, doc_id, row["seq_num"], year, year)
        ).fetchone()

        if collision:
            new_doc_number, new_seq = get_next_doc_number(
                user_id, row["doc_type"], row["doc_date"], conn
            )
            conn.execute(
                "UPDATE documents SET deleted_at = NULL, seq_num = ?, doc_number = ? WHERE id = ? AND user_id = ?",
                (new_seq, new_doc_number, doc_id, user_id)
            )
        else:
            conn.execute(
                "UPDATE documents SET deleted_at = NULL WHERE id = ? AND user_id = ?",
                (doc_id, user_id)
            )
        conn.commit()
        return True
    finally:
        conn.close()


def permanently_delete_document(user_id, doc_id):
    """Permanently delete a document (no recovery)."""
    conn = get_connection()
    conn.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
    conn.commit()
    conn.close()


def get_deleted_documents(user_id):
    """Get all soft-deleted documents for a user (trash)."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT d.*, c.name as client_name,
           ROUND(COALESCE((SELECT SUM(di.total) FROM document_items di WHERE di.document_id = d.id), 0) * (1 + d.vat_rate / 100.0), 2) as total_with_vat
           FROM documents d
           JOIN clients c ON d.client_id = c.id
           WHERE d.user_id = ? AND d.deleted_at IS NOT NULL
           ORDER BY d.deleted_at DESC""",
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def purge_old_deleted_documents():
    """Permanently delete documents that have been in trash for more than 7 days."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM documents WHERE deleted_at IS NOT NULL AND deleted_at < datetime('now', '-7 days')"
    )
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
                email: str = "", phone: str = "", is_admin: bool = False,
                must_change_password: bool = False,
                tier: str = "free") -> int:
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO users (username, email, phone, password_hash, display_name,
           is_admin, must_change_password, tier, subscription_status, subscription_start)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
        (username.lower().strip(), email.strip(), phone.strip(), _hash_password(password),
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
    if not row:
        row = conn.execute("SELECT * FROM users WHERE email = ?",
                           (username.strip().lower(),)).fetchone()
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


def update_user_profile(user_id: int, display_name: str = None, email: str = None, phone: str = None):
    conn = get_connection()
    if display_name is not None:
        conn.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name, user_id))
    if email is not None:
        conn.execute("UPDATE users SET email = ? WHERE id = ?", (email.strip(), user_id))
    if phone is not None:
        conn.execute("UPDATE users SET phone = ? WHERE id = ?", (phone.strip(), user_id))
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
        "SELECT COUNT(*) as cnt FROM documents WHERE user_id = ? AND deleted_at IS NULL AND doc_date >= ?",
        (user_id, week_ago)
    ).fetchone()
    docs_last_7_days = row["cnt"] if row else 0

    # Total revenue (sum of sell document totals)
    row = conn.execute("""
        SELECT COALESCE(SUM(di.quantity * di.price_per_unit * (1 + d.vat_rate / 100)), 0) as total
        FROM documents d
        JOIN document_items di ON di.document_id = d.id
        WHERE d.user_id = ? AND d.deleted_at IS NULL AND d.doc_type = 'sell'
    """, (user_id,)).fetchone()
    total_revenue = row["total"] if row else 0

    # Revenue last 7 days
    row = conn.execute("""
        SELECT COALESCE(SUM(di.quantity * di.price_per_unit * (1 + d.vat_rate / 100)), 0) as total
        FROM documents d
        JOIN document_items di ON di.document_id = d.id
        WHERE d.user_id = ? AND d.deleted_at IS NULL AND d.doc_type = 'sell' AND d.doc_date >= ?
    """, (user_id, week_ago)).fetchone()
    revenue_last_7_days = row["total"] if row else 0

    # Most used client (by document count)
    row = conn.execute("""
        SELECT c.name, COUNT(*) as cnt
        FROM documents d
        JOIN clients c ON d.client_id = c.id
        WHERE d.user_id = ? AND d.deleted_at IS NULL
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
        WHERE d.user_id = ? AND d.deleted_at IS NULL AND d.doc_type = 'sell'
        GROUP BY di.product_id
        ORDER BY total_qty DESC
        LIMIT 1
    """, (user_id,)).fetchone()
    top_product = {"name": row["name"], "quantity": row["total_qty"], "unit": row["unit"]} if row else None

    # Total documents
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM documents WHERE user_id = ? AND deleted_at IS NULL", (user_id,)
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


def _shift_date_back(d: datetime.date, months: int = 0, years: int = 0) -> datetime.date:
    """Shift a date back by n months and/or years. Clamps day to last day of target month
    when the source day doesn't exist (e.g. May 31 → April 30, Feb 29 → Feb 28)."""
    import calendar
    year = d.year - years
    month = d.month - months
    while month <= 0:
        month += 12
        year -= 1
    max_day = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, min(d.day, max_day))


def _is_full_month(d_from: datetime.date, d_to: datetime.date) -> bool:
    import calendar
    return (
        d_from.day == 1
        and d_from.year == d_to.year
        and d_from.month == d_to.month
        and d_to.day == calendar.monthrange(d_to.year, d_to.month)[1]
    )


def _is_full_year(d_from: datetime.date, d_to: datetime.date) -> bool:
    return (
        d_from.year == d_to.year
        and d_from.month == 1 and d_from.day == 1
        and d_to.month == 12 and d_to.day == 31
    )


def get_dashboard_stats_range(user_id: int, date_from: str, date_to: str, compare_mode: str = "auto") -> dict:
    """Get dashboard statistics for a user within a date range.

    compare_mode: 'auto' | 'month' | 'year'
      - 'month': previous period = same date range shifted back 1 calendar month
                 (May 1–17 → April 1–17, May 12–28 → April 12–28).
                 If the period is a *full* calendar month, snaps to the full prior
                 calendar month (April 1–30 → March 1–31, not March 1–30).
      - 'year':  previous period = same date range shifted back 1 calendar year.
                 Full-year periods snap to the full prior calendar year.
      - 'auto':  full-year → year; full-month or span ≤ 31 days → month; else year.
    """
    import calendar
    conn = get_connection()
    today_str = datetime.date.today().isoformat()

    d_from = datetime.date.fromisoformat(date_from)
    d_to = datetime.date.fromisoformat(date_to)
    period_days = (d_to - d_from).days + 1

    if compare_mode == "auto":
        if _is_full_year(d_from, d_to):
            compare_mode = "year"
        elif _is_full_month(d_from, d_to) or period_days <= 31:
            compare_mode = "month"
        else:
            compare_mode = "year"

    if compare_mode == "year":
        if _is_full_year(d_from, d_to):
            prev_from = datetime.date(d_from.year - 1, 1, 1)
            prev_to = datetime.date(d_to.year - 1, 12, 31)
        else:
            prev_from = _shift_date_back(d_from, years=1)
            prev_to = _shift_date_back(d_to, years=1)
    else:
        compare_mode = "month"
        if _is_full_month(d_from, d_to):
            prev_from = _shift_date_back(d_from, months=1)
            prev_to = datetime.date(
                prev_from.year, prev_from.month,
                calendar.monthrange(prev_from.year, prev_from.month)[1],
            )
        else:
            prev_from = _shift_date_back(d_from, months=1)
            prev_to = _shift_date_back(d_to, months=1)

    prev_from_str = prev_from.isoformat()
    prev_to_str = prev_to.isoformat()

    # Revenue, expenses, doc count, and average in one pass
    row = conn.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN d.doc_type='sell' THEN di.quantity * di.price_per_unit * (1 + d.vat_rate / 100) ELSE 0 END), 0) as revenue,
            COALESCE(SUM(CASE WHEN d.doc_type='buy'  THEN di.quantity * di.price_per_unit * (1 + d.vat_rate / 100) ELSE 0 END), 0) as expenses,
            COUNT(DISTINCT d.id) as doc_count
        FROM documents d
        JOIN document_items di ON di.document_id = d.id
        WHERE d.user_id = ? AND d.deleted_at IS NULL AND d.doc_date >= ? AND d.doc_date <= ?
    """, (user_id, date_from, date_to)).fetchone()
    total_revenue = row["revenue"] if row else 0
    total_expenses = row["expenses"] if row else 0
    doc_count = row["doc_count"] if row else 0

    # Previous period revenue + doc count for comparison
    prev_row = conn.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN d.doc_type='sell' THEN di.quantity * di.price_per_unit * (1 + d.vat_rate / 100) ELSE 0 END), 0) as revenue,
            COUNT(DISTINCT d.id) as doc_count
        FROM documents d
        JOIN document_items di ON di.document_id = d.id
        WHERE d.user_id = ? AND d.deleted_at IS NULL AND d.doc_date >= ? AND d.doc_date <= ?
    """, (user_id, prev_from_str, prev_to_str)).fetchone()
    prev_revenue = prev_row["revenue"] if prev_row else 0
    prev_doc_count = prev_row["doc_count"] if prev_row else 0

    # Average sell invoice value
    row = conn.execute("""
        SELECT AVG(inv_total) as avg_val FROM (
            SELECT SUM(di.quantity * di.price_per_unit * (1 + d.vat_rate / 100)) as inv_total
            FROM documents d
            JOIN document_items di ON di.document_id = d.id
            WHERE d.user_id = ? AND d.deleted_at IS NULL AND d.doc_type = 'sell' AND d.doc_date >= ? AND d.doc_date <= ?
            GROUP BY d.id
        )
    """, (user_id, date_from, date_to)).fetchone()
    avg_invoice = row["avg_val"] if row and row["avg_val"] else 0

    # Unpaid + overdue in one query
    row = conn.execute("""
        SELECT
            COALESCE(SUM(inv_total), 0) as unpaid_total,
            SUM(CASE WHEN payment_due_date IS NOT NULL AND payment_due_date != '' AND payment_due_date < ? THEN 1 ELSE 0 END) as overdue_count,
            COALESCE(SUM(CASE WHEN payment_due_date IS NOT NULL AND payment_due_date != '' AND payment_due_date < ? THEN inv_total ELSE 0 END), 0) as overdue_total
        FROM (
            SELECT d.id, d.payment_due_date,
                   SUM(di.quantity * di.price_per_unit * (1 + d.vat_rate / 100)) as inv_total
            FROM documents d
            JOIN document_items di ON di.document_id = d.id
            WHERE d.user_id = ? AND d.deleted_at IS NULL AND d.doc_type = 'sell' AND d.status = 'issued'
            GROUP BY d.id
        )
    """, (today_str, today_str, user_id)).fetchone()
    unpaid_total = row["unpaid_total"] if row and row["unpaid_total"] else 0
    overdue_count = row["overdue_count"] if row and row["overdue_count"] else 0
    overdue_total = row["overdue_total"] if row and row["overdue_total"] else 0

    # Top client
    row = conn.execute("""
        SELECT c.name, COUNT(DISTINCT d.id) as cnt,
               COALESCE(SUM(di.quantity * di.price_per_unit * (1 + d.vat_rate / 100)), 0) as revenue
        FROM documents d
        JOIN document_items di ON di.document_id = d.id
        JOIN clients c ON d.client_id = c.id
        WHERE d.user_id = ? AND d.deleted_at IS NULL AND d.doc_type = 'sell' AND d.doc_date >= ? AND d.doc_date <= ?
        GROUP BY d.client_id
        ORDER BY revenue DESC
        LIMIT 1
    """, (user_id, date_from, date_to)).fetchone()
    top_client = {"name": row["name"], "count": row["cnt"], "revenue": row["revenue"]} if row else None

    # Daily revenue for chart
    rows = conn.execute("""
        SELECT d.doc_date,
               COALESCE(SUM(di.quantity * di.price_per_unit * (1 + d.vat_rate / 100)), 0) as daily_total
        FROM documents d
        JOIN document_items di ON di.document_id = d.id
        WHERE d.user_id = ? AND d.deleted_at IS NULL AND d.doc_type = 'sell' AND d.doc_date >= ? AND d.doc_date <= ?
        GROUP BY d.doc_date
        ORDER BY d.doc_date
    """, (user_id, date_from, date_to)).fetchall()
    daily_revenue = [{"date": r["doc_date"], "total": round(r["daily_total"], 2)} for r in rows]

    # Revenue change percentage vs previous period
    if prev_revenue > 0:
        revenue_change = round(((total_revenue - prev_revenue) / prev_revenue) * 100, 1)
    elif total_revenue > 0:
        revenue_change = 100.0
    else:
        revenue_change = 0.0

    if prev_doc_count > 0:
        doc_count_change = round(((doc_count - prev_doc_count) / prev_doc_count) * 100, 1)
    elif doc_count > 0:
        doc_count_change = 100.0
    else:
        doc_count_change = 0.0

    conn.close()
    return {
        "total_revenue": total_revenue,
        "total_expenses": total_expenses,
        "unpaid_total": unpaid_total,
        "doc_count": doc_count,
        "avg_invoice": avg_invoice,
        "top_client": top_client,
        "overdue_count": overdue_count,
        "overdue_total": overdue_total,
        "daily_revenue": daily_revenue,
        "revenue_change": revenue_change,
        "prev_revenue": prev_revenue,
        "doc_count_change": doc_count_change,
        "prev_doc_count": prev_doc_count,
        "compare_mode": compare_mode,
        "prev_from": prev_from_str,
        "prev_to": prev_to_str,
    }


def get_user_document_count(user_id: int) -> int:
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as cnt FROM documents WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return row["cnt"]


def get_user_max_seq(user_id: int, year: int = None) -> int:
    """Highest seq_num used so far. Used by the 'start from' setting validation
    to prevent the user from picking a number that would collide with existing docs.

    If year is given, scopes to that year (matches type1 yearly reset).
    Otherwise returns the overall maximum (matches type3 sequential).
    """
    conn = get_connection()
    if year is None:
        row = conn.execute(
            "SELECT MAX(seq_num) as max_num FROM documents WHERE user_id = ? AND deleted_at IS NULL",
            (user_id,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT MAX(seq_num) as max_num FROM documents WHERE user_id = ? AND deleted_at IS NULL AND strftime('%Y', doc_date) = ?",
            (user_id, str(year))
        ).fetchone()
    conn.close()
    return (row["max_num"] or 0) if row else 0


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
    "free": {
        "max_documents": 5, "max_clients": 5, "max_products": 5,
        "max_emails_month": 0, "recurring": False, "max_recurring": 0,
        "all_templates": False,
        "einvoice": False, "accounting_export": False,
        "label": "Bezmaksas",
        "price_monthly": 0, "price_yearly": 0,
    },
    "mini": {
        "max_documents": 50, "max_clients": 25, "max_products": 25,
        "max_emails_month": 10, "recurring": False, "max_recurring": 0,
        "all_templates": False,
        "einvoice": False, "accounting_export": False,
        "label": "Mini",
        "price_monthly": 299, "price_yearly": 2900,  # cents
    },
    "starter": {
        "max_documents": 500, "max_clients": 100, "max_products": 200,
        "max_emails_month": 50, "recurring": True, "max_recurring": 3,
        "all_templates": True,
        "einvoice": True, "accounting_export": True,
        "label": "Pamata",
        "price_monthly": 599, "price_yearly": 5900,  # cents
    },
    "business": {
        "max_documents": 5000, "max_clients": 500, "max_products": 1000,
        "max_emails_month": 0, "recurring": True, "max_recurring": 0,  # 0 = unlimited
        "all_templates": True,
        "einvoice": True, "accounting_export": True,
        "label": "Bizness",
        "price_monthly": 1999, "price_yearly": 19900,  # cents
    },
    "lifetime": {
        "max_documents": 5000, "max_clients": 500, "max_products": 1000,
        "max_emails_month": 0, "recurring": True, "max_recurring": 0,  # 0 = unlimited
        "all_templates": True,
        "einvoice": True, "accounting_export": True,
        "label": "Mūža licence",
        "price_monthly": 0, "price_yearly": 0, "price_lifetime": 49900,  # cents
    },
    "admin": {
        "max_documents": 999999, "max_clients": 999999, "max_products": 999999,
        "max_emails_month": 0, "recurring": True, "max_recurring": 0,
        "all_templates": True,
        "einvoice": True, "accounting_export": True,
        "label": "Administrators",
        "price_monthly": 0, "price_yearly": 0,
    },
}


def get_tier_limits(tier):
    return TIER_LIMITS.get(tier, TIER_LIMITS["free"])


def count_active_recurring(user_id):
    """Count active recurring invoices for a user."""
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM recurring_invoices WHERE user_id = ? AND active = 1",
        (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


def count_lifetime_users():
    """Count users with lifetime tier."""
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM users WHERE tier = 'lifetime'").fetchone()[0]
    conn.close()
    return count


def update_user_subscription(user_id: int, tier: str, billing_cycle: str = "",
                             everypay_token: str = "", everypay_payment_ref: str = "",
                             subscription_status: str = "active"):
    """Update user subscription fields after EveryPay payment events."""
    conn = get_connection()
    limits = get_tier_limits(tier)
    conn.execute(
        """UPDATE users SET tier = ?, billing_cycle = ?, everypay_token = ?,
           everypay_payment_ref = ?, subscription_status = ?,
           subscription_start = COALESCE(subscription_start, ?),
           max_documents = ?, max_clients = ?, max_products = ?
           WHERE id = ?""",
        (tier, billing_cycle, everypay_token, everypay_payment_ref,
         subscription_status, datetime.date.today().isoformat(),
         limits["max_documents"], limits["max_clients"], limits["max_products"],
         user_id)
    )
    conn.commit()
    conn.close()


def get_user_by_everypay_token(token: str):
    """Find user by their stored EveryPay card token."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE everypay_token = ?",
                       (token,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_users_due_for_renewal():
    """Get users with active paid subscriptions that are due for renewal."""
    conn = get_connection()
    today = datetime.date.today().isoformat()
    rows = conn.execute(
        """SELECT * FROM users
           WHERE tier != 'free' AND tier != 'lifetime' AND tier != 'admin'
           AND subscription_status IN ('active', 'past_due')
           AND everypay_token != ''
           AND (subscription_end IS NULL OR subscription_end <= ?)""",
        (today,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def extend_subscription(user_id: int, days: int, payment_ref: str):
    """After a successful renewal charge: push subscription_end forward,
    record the new payment_ref, reset retry counter, mark active."""
    conn = get_connection()
    today = datetime.date.today()
    row = conn.execute("SELECT subscription_end FROM users WHERE id = ?", (user_id,)).fetchone()
    current_end = None
    if row and row["subscription_end"]:
        try:
            current_end = datetime.date.fromisoformat(row["subscription_end"])
        except ValueError:
            current_end = None
    # Extend from whichever is later: existing end or today (so a late charge
    # doesn't lose paid time, but an early one doesn't extend by less than days)
    base = max(current_end, today) if current_end else today
    new_end = (base + datetime.timedelta(days=days)).isoformat()
    conn.execute(
        """UPDATE users
           SET subscription_end = ?,
               subscription_status = 'active',
               renewal_attempts = 0,
               last_renewal_attempt = CURRENT_TIMESTAMP,
               everypay_payment_ref = ?
           WHERE id = ?""",
        (new_end, payment_ref, user_id)
    )
    conn.commit()
    conn.close()
    return new_end


def record_renewal_failure(user_id: int):
    """Increment retry counter and mark past_due. Returns the new attempt count."""
    conn = get_connection()
    conn.execute(
        """UPDATE users
           SET renewal_attempts = renewal_attempts + 1,
               last_renewal_attempt = CURRENT_TIMESTAMP,
               subscription_status = 'past_due'
           WHERE id = ?""",
        (user_id,)
    )
    row = conn.execute("SELECT renewal_attempts FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.commit()
    conn.close()
    return (row["renewal_attempts"] if row else 0)


def cancel_user_subscription(user_id: int):
    """Downgrade user to free tier on subscription cancellation."""
    conn = get_connection()
    limits = get_tier_limits("free")
    conn.execute(
        """UPDATE users SET tier = 'free', billing_cycle = '',
           everypay_payment_ref = '', subscription_status = 'cancelled',
           subscription_end = ?,
           max_documents = ?, max_clients = ?, max_products = ?
           WHERE id = ?""",
        (datetime.date.today().isoformat(),
         limits["max_documents"], limits["max_clients"], limits["max_products"],
         user_id)
    )
    conn.commit()
    conn.close()


def get_user_resource_counts(user_id: int) -> dict:
    """Get current usage counts for a user.
    Documents are counted per calendar month; clients/products are totals."""
    conn = get_connection()
    month_start = datetime.date.today().replace(day=1).isoformat()
    docs = conn.execute(
        "SELECT COUNT(*) as cnt FROM documents WHERE user_id = ? AND deleted_at IS NULL AND doc_type != 'offer' AND created_at >= ?",
        (user_id, month_start)
    ).fetchone()
    clients = conn.execute("SELECT COUNT(*) as cnt FROM clients WHERE user_id = ? AND active = 1 AND one_time = 0", (user_id,)).fetchone()
    products = conn.execute("SELECT COUNT(*) as cnt FROM products WHERE user_id = ? AND active = 1", (user_id,)).fetchone()
    conn.close()
    return {
        "documents": docs["cnt"] if docs else 0,
        "clients": clients["cnt"] if clients else 0,
        "products": products["cnt"] if products else 0,
    }


def get_emails_sent_this_month(user_id: int) -> int:
    """Count emails sent by user in the current calendar month."""
    conn = get_connection()
    today = datetime.date.today()
    month_start = today.replace(day=1).isoformat()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM email_log WHERE user_id = ? AND sent_at >= ?",
        (user_id, month_start)
    ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


def log_email_sent(user_id: int, document_id: int, recipient: str, source: str = "manual"):
    """Record an email send event."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO email_log (user_id, document_id, recipient, source) VALUES (?, ?, ?, ?)",
        (user_id, document_id, recipient, source)
    )
    conn.commit()
    conn.close()


def get_email_log(user_id: int, source: str = None) -> list:
    """Get email log entries for a user, optionally filtered by source."""
    conn = get_connection()
    if source:
        rows = conn.execute(
            """SELECT e.id, e.document_id, e.recipient, e.source, e.sent_at,
                      d.doc_number, d.doc_type, c.name as client_name
               FROM email_log e
               LEFT JOIN documents d ON e.document_id = d.id
               LEFT JOIN clients c ON d.client_id = c.id
               WHERE e.user_id = ?  AND e.source = ?
               ORDER BY e.sent_at DESC""",
            (user_id, source)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT e.id, e.document_id, e.recipient, e.source, e.sent_at,
                      d.doc_number, d.doc_type, c.name as client_name
               FROM email_log e
               LEFT JOIN documents d ON e.document_id = d.id
               LEFT JOIN clients c ON d.client_id = c.id
               WHERE e.user_id = ?
               ORDER BY e.sent_at DESC""",
            (user_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def log_event(user_id: int, event_type: str, document_id: int = None,
              client_id: int = None, meta: dict = None):
    """Record an activity event for the user's feed.

    event_type: 'document_created' | 'document_sent'
    meta: optional dict (serialized as JSON). Use 'send_type' = 'manual'|'recurring'
          for document_sent events, 'recipient' for the recipient email.
    """
    import json as _json
    meta_json = _json.dumps(meta) if meta else None
    conn = get_connection()
    conn.execute(
        """INSERT INTO events (user_id, event_type, document_id, client_id, meta)
           VALUES (?, ?, ?, ?, ?)""",
        (user_id, event_type, document_id, client_id, meta_json)
    )
    conn.commit()
    conn.close()


def get_recent_events(user_id: int, limit: int = 10) -> list:
    """Get recent activity events joined with document + client info."""
    import json as _json
    conn = get_connection()
    rows = conn.execute(
        """SELECT e.id, e.event_type, e.document_id, e.client_id, e.meta, e.created_at,
                  d.doc_number, d.doc_type,
                  COALESCE(c.name, dc.name) as client_name,
                  (SELECT COALESCE(SUM(di.quantity * di.price_per_unit * (1 + d.vat_rate / 100)), 0)
                   FROM document_items di WHERE di.document_id = d.id) as amount
           FROM events e
           LEFT JOIN documents d ON e.document_id = d.id
           LEFT JOIN clients c ON e.client_id = c.id
           LEFT JOIN clients dc ON d.client_id = dc.id
           WHERE e.user_id = ?
           ORDER BY e.created_at DESC
           LIMIT ?""",
        (user_id, limit)
    ).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        if d.get('meta'):
            try:
                d['meta'] = _json.loads(d['meta'])
            except Exception:
                d['meta'] = {}
        else:
            d['meta'] = {}
        out.append(d)
    return out


# --- Recurring Invoices ---

def create_recurring_invoice(user_id, doc_type, client_id, vat_rate, notes, template,
                             frequency, next_run, send_email, items_json,
                             email_subject="", email_body=""):
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO recurring_invoices
           (user_id, doc_type, client_id, vat_rate, notes, template, frequency,
            next_run, send_email, email_subject, email_body, items_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, doc_type, client_id, vat_rate, notes, template, frequency, next_run,
         1 if send_email else 0, email_subject, email_body, items_json)
    )
    rid = cursor.lastrowid
    conn.commit()
    conn.close()
    return rid


def update_recurring_invoice(user_id, recurring_id, doc_type, client_id, vat_rate, notes,
                             template, frequency, next_run, send_email, items_json,
                             email_subject="", email_body=""):
    conn = get_connection()
    conn.execute(
        """UPDATE recurring_invoices
           SET doc_type = ?, client_id = ?, vat_rate = ?, notes = ?, template = ?,
               frequency = ?, next_run = ?, send_email = ?, email_subject = ?,
               email_body = ?, items_json = ?
           WHERE id = ? AND user_id = ?""",
        (doc_type, client_id, vat_rate, notes, template, frequency, next_run,
         1 if send_email else 0, email_subject, email_body, items_json,
         recurring_id, user_id)
    )
    conn.commit()
    conn.close()


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


# --- Accounting Export ---

def get_documents_for_export(user_id, doc_type=None, date_from=None, date_to=None):
    """Get documents with full client data and line items for accounting export.
    Returns list of dicts, each with 'doc', 'client', and 'items' keys."""
    conn = get_connection()

    query = """SELECT d.*, c.name as client_name, c.reg_number as client_reg_number,
               c.vat_number as client_vat_number, c.vat_payer as client_vat_payer,
               c.legal_address as client_address,
               c.bank_name as client_bank, c.bank_account as client_account,
               c.contact_person as client_contact, c.phone as client_phone,
               c.email as client_email
               FROM documents d
               JOIN clients c ON d.client_id = c.id
               WHERE d.user_id = ? AND d.deleted_at IS NULL"""
    params = [user_id]

    if doc_type:
        query += " AND d.doc_type = ?"
        params.append(doc_type)
    if date_from:
        query += " AND d.doc_date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND d.doc_date <= ?"
        params.append(date_to)

    query += " ORDER BY d.doc_date ASC, d.id ASC"
    docs = conn.execute(query, params).fetchall()

    results = []
    for doc in docs:
        doc_dict = dict(doc)
        items = conn.execute(
            """SELECT di.*,
                      COALESCE(p.name, di.description, '') as product_name,
                      COALESCE(p.unit, di.unit) as product_unit
               FROM document_items di
               LEFT JOIN products p ON di.product_id = p.id
               WHERE di.document_id = ?
               ORDER BY di.id""",
            (doc_dict["id"],)
        ).fetchall()
        doc_dict["items"] = [dict(i) for i in items]
        results.append(doc_dict)

    conn.close()
    return results
