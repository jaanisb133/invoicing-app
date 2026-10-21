"""Fictional account for the landing-page footage: SIA "Ziemeļu Kadrs" (a photo studio) billing SIA "Bērzu Darbnīca".
Run with VREKINI_DB_PATH pointing at a scratch file. User paraugs / paraugs12345."""
import datetime as dt, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from app import database as db
db.init_db()
if db.get_user_by_username("paraugs"):
    print("already seeded"); sys.exit(0)
uid = db.create_user("paraugs", "paraugs12345", display_name="Anna", tier="business")
for k, v in {"company_name": 'SIA "Ziemeļu Kadrs"', "reg_number": "40203999902", "vat_number": "LV40203999902",
             "legal_address": "Valmiera, Rīgas iela 99, LV-4201", "bank_name": 'AS "SEB banka"',
             "bank_account": "LV00UNLA0000000000000", "is_vat_payer": "1", "default_vat_rate": "21",
             "payment_due_days": "14", "default_template": "modern", "email": "rekini@example.lv",
             "status_tracking": "1", "tours_seen": "dashboard,editor"}.items():
    db.set_user_setting(uid, k, v)
cl = [('SIA "Bērzu Darbnīca"', "40203999901", "LV40203999901", "Rīga, Ganību dambis 99, LV-1005"),
      ('SIA "Lejas Nami"', "40203999904", "LV40203999904", "Jelgava, Lielā iela 99, LV-3001"),
      ('IK "J. Ozols"', "40203999905", "", "Cēsis, Raunas iela 98, LV-4101")]
cids = []
for name, reg, vat, addr in cl:
    c = db.add_client(uid, name, reg_number=reg, vat_number=vat, vat_payer=1 if vat else 0, legal_address=addr)
    cids.append(c if isinstance(c, int) else c["id"])
# Services under the general VAT rules: a construction service between two VAT payers
# would be reverse charge, and the sample shows 21 %
prods = [("Produktu fotografēšana", "gab.", 8.50), ("Attēlu apstrāde", "st.", 35.00), ("Fotosesija", "st.", 60.00)]
pids = []
for name, unit, _ in prods:
    p = db.add_product(uid, name, unit); pids.append(p if isinstance(p, int) else p["id"])
today = dt.date.today()
# Earlier invoices give the products their last prices and the clients a history
for days, ci, lines in ((40, 1, [(0, 300), (1, 10)]), (25, 0, [(0, 80)]), (9, 2, [(2, 1)])):
    d = today - dt.timedelta(days=days)
    items = [{"product_id": pids[i], "description": "", "quantity": q, "unit": prods[i][1], "price_per_unit": prods[i][2]} for i, q in lines]
    doc_id, _ = db.create_document(uid, "sell", cids[ci], d.isoformat(), items, vat_rate=21.0,
                                   payment_due_date=(d + dt.timedelta(days=14)).isoformat())
    db.update_document_status(uid, doc_id, "paid")
print("seeded user paraugs id", uid)
