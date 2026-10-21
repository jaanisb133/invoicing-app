"""Render the downloadable sample for /celvedis/rekina-paraugs from the footage account.

    VREKINI_DB_PATH=/tmp/footage.db python scripts/footage/seed.py
    VREKINI_DB_PATH=/tmp/footage.db python scripts/footage/sample_pdf.py

The guide walks through this exact invoice (Nr. 26-041, 1 488,30 €), so change both together.
"""
import datetime as dt
import os
import shutil
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)
from app import database as db, pdf_generator as pg

uid = db.get_user_by_username("paraugs")["id"]
db.set_user_setting(uid, "electronic_doc", "1")  # the setup default
conn = db.get_connection()
client = conn.execute("SELECT id FROM clients WHERE user_id=? AND name LIKE '%Bērzu%'", (uid,)).fetchone()[0]
prods = {r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM products WHERE user_id=?", (uid,))}
conn.close()
d = dt.date.today()
items = [{"product_id": prods["Produktu fotografēšana"], "description": "", "quantity": 120, "unit": "gab.", "price_per_unit": 8.50},
         {"product_id": prods["Attēlu apstrāde"], "description": "", "quantity": 6, "unit": "st.", "price_per_unit": 35.00}]
doc_id, _ = db.create_document(uid, "sell", client, d.isoformat(), items, vat_rate=21.0,
                               payment_due_date=(d + dt.timedelta(days=14)).isoformat())
conn = db.get_connection()
conn.execute("UPDATE documents SET doc_number='26-041' WHERE id=?", (doc_id,))
conn.commit()
conn.close()
path = pg.generate_invoice_pdf(doc_id, template="modern")
shutil.copy(path, os.path.join(ROOT, "app", "static", "guides", "rekina-paraugs.pdf"))
os.remove(path)
print("wrote app/static/guides/rekina-paraugs.pdf")
