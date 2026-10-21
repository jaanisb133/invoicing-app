"""A lived-in fictional account for portfolio screenshots (scripts/footage/screens.py).

SIA "Ziemeļu Kadrs", a photo studio in Valmiera, with invoices since January last year
(so this year compares with a real last year) to eight fictional clients: paid, awaiting payment, two overdue, a credit note, offers,
a monthly recurring invoice, and the e-mails and activity that go with them. Dates are
relative to today, so the dashboard always reads as current. Deterministic.

    VREKINI_DB_PATH=/tmp/showcase.db python scripts/footage/showcase.py
    User: paraugs / paraugs12345
"""
import datetime as dt
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from app import database as db

db.init_db()
if db.get_user_by_username("paraugs"):
    print("already seeded")
    sys.exit(0)

rng = random.Random(1740)
today = dt.date.today()
uid = db.create_user("paraugs", "paraugs12345", display_name="Anna", tier="business")
for k, v in {"company_name": 'SIA "Ziemeļu Kadrs"', "reg_number": "40203999902", "vat_number": "LV40203999902",
             "legal_address": "Valmiera, Rīgas iela 99, LV-4201", "bank_name": 'AS "SEB banka"',
             "bank_account": "LV00UNLA0000000000000", "is_vat_payer": "1", "default_vat_rate": "21",
             "payment_due_days": "14", "default_template": "modern", "email": "rekini@example.lv",
             "company_email": "studija@example.lv", "company_phone": "+371 20 000 000",
             "company_website": "ziemelukadrs.example", "status_tracking": "1",
             "tours_seen": "dashboard,editor", "onboarding_hidden": "1"}.items():
    db.set_user_setting(uid, k, v)

# name, reg. no., VAT no., address, e-mail
CLIENTS = [
    ('SIA "Bērzu Darbnīca"', "40203999901", "LV40203999901", "Rīga, Ganību dambis 99, LV-1005", "birojs@berzu.example"),
    ('SIA "Lejas Nami"', "40203999904", "LV40203999904", "Jelgava, Lielā iela 99, LV-3001", "info@lejasnami.example"),
    ('IK "J. Ozols"', "40203999905", "", "Cēsis, Raunas iela 98, LV-4101", "janis@ozols.example"),
    ('SIA "Sētas Kafejnīca"', "40203999906", "LV40203999906", "Valmiera, Purva iela 98, LV-4201", "kafe@setas.example"),
    ('SIA "Rasas Ziedi"', "40203999907", "LV40203999907", "Sigulda, Pils iela 97, LV-2150", "ziedi@rasas.example"),
    ('SIA "Ozolkalna Keramika"', "40203999908", "LV40203999908", "Smiltene, Dārza iela 96, LV-4729", "darbnica@ozolkalns.example"),
    ('Biedrība "Gaujmalas Skrējēji"', "40008999909", "", "Valmiera, Upes iela 95, LV-4201", "valde@gaujmala.example"),
    ('SIA "Vidzemes Ādas Darbnīca"', "40203999910", "LV40203999910", "Valmiera, Tirgus iela 94, LV-4201", "pasutijumi@vad.example"),
]
cids = []
for name, reg, vat, addr, mail in CLIENTS:
    c = db.add_client(uid, name, reg_number=reg, vat_number=vat, vat_payer=1 if vat else 0, legal_address=addr)
    cid = c if isinstance(c, int) else c["id"]
    conn = db.get_connection()
    conn.execute("UPDATE clients SET email = ? WHERE id = ?", (mail, cid))
    conn.commit()
    conn.close()
    cids.append(cid)

PRODUCTS = [("Produktu fotografēšana", "gab.", 8.50), ("Attēlu apstrāde", "st.", 35.00),
            ("Fotosesija", "st.", 60.00), ("Pasākuma fotografēšana", "st.", 75.00),
            ("Video klips līdz 60 s", "gab.", 420.00), ("Sociālo tīklu foto komplekts", "gab.", 180.00)]
pids = []
for name, unit, _ in PRODUCTS:
    p = db.add_product(uid, name, unit)
    pids.append(p if isinstance(p, int) else p["id"])


def lines_for(ci):
    """What each client typically buys."""
    pick = {
        0: [(0, rng.choice([40, 60, 80, 120])), (1, rng.choice([4, 6, 8]))],
        1: [(2, rng.choice([2, 3, 4])), (1, rng.choice([2, 3]))],
        2: [(2, rng.choice([1, 2]))],
        3: [(5, 1)],
        4: [(0, rng.choice([20, 30, 45])), (1, 2)],
        5: [(0, rng.choice([30, 50, 70])), (1, rng.choice([3, 5]))],
        6: [(3, rng.choice([3, 4, 5]))],
        7: [(0, rng.choice([25, 40])), (4, 1)] if rng.random() < .35 else [(0, rng.choice([25, 40, 60]))],
    }[ci]
    return [{"product_id": pids[i], "description": "", "quantity": q, "unit": PRODUCTS[i][1],
             "price_per_unit": PRODUCTS[i][2]} for i, q in pick]


def at(day, hh, mm):
    return f"{day.isoformat()} {hh:02d}:{mm:02d}:00"


def backdate(doc_id, created, sent=None):
    conn = db.get_connection()
    conn.execute("UPDATE documents SET created_at = ? WHERE id = ?", (created, doc_id))
    if sent:
        conn.execute("UPDATE documents SET sent_at = ? WHERE id = ?", (sent, doc_id))
        conn.execute("UPDATE email_log SET sent_at = ? WHERE document_id = ?", (sent, doc_id))
    conn.execute("UPDATE events SET created_at = ? WHERE document_id = ? AND event_type = 'document_created'", (created, doc_id))
    if sent:
        conn.execute("UPDATE events SET created_at = ? WHERE document_id = ? AND event_type = 'document_sent'", (sent, doc_id))
    conn.commit()
    conn.close()


def invoice(day, ci, items=None, send=True, recurring=False):
    items = items or lines_for(ci)
    doc_id, _ = db.create_document(uid, "sell", cids[ci], day.isoformat(), items, vat_rate=21.0,
                                   payment_due_date=(day + dt.timedelta(days=14)).isoformat())
    created = at(day, rng.randint(8, 11), rng.randint(0, 59))
    db.log_event(uid, "document_created", document_id=doc_id, client_id=cids[ci],
                 meta={"source": "recurring"} if recurring else None)
    sent = None
    if send:
        db.log_email_sent(uid, doc_id, CLIENTS[ci][4], source="recurring" if recurring else "manual")
        db.log_event(uid, "document_sent", document_id=doc_id, client_id=cids[ci],
                     meta={"send_type": "recurring" if recurring else "manual", "recipient": CLIENTS[ci][4]})
        sent = at(day, rng.randint(12, 16), rng.randint(0, 59))
    backdate(doc_id, created, sent)
    return doc_id


def gross(items):
    return sum(i["quantity"] * i["price_per_unit"] for i in items) * 1.21


# A studio that grows, busy before Christmas and in summer, quiet in January. Every invoice is planned first and created in date order, so numbers run
# with dates the way a real series must.
TARGETS = [2100, 2300, 2700, 2900, 3300, 3600, 3200, 3400, 3800, 3900, 3600, 4400,   # last year
           2600, 2900, 3500, 3800, 4300, 4700, 4100, 4500, 5100, 5200, 4800, 5600]   # this year
LATE = [(30, 1, [{"product_id": pids[2], "description": "", "quantity": 4, "unit": "st.", "price_per_unit": 60.0},
                 {"product_id": pids[1], "description": "", "quantity": 3, "unit": "st.", "price_per_unit": 35.0}]),
        (19, 4, None)]
plan = []
month = dt.date(today.year - 1, 1, 1)
mi = 0
while month <= today:
    nxt = (month + dt.timedelta(days=32)).replace(day=1)
    last = min(nxt - dt.timedelta(days=1), today - dt.timedelta(days=2))
    target = TARGETS[min(mi, len(TARGETS) - 1)]
    if month.year == today.year and month.month == today.month:
        target = target * today.day / 31
    total = 0.0
    if dt.date(month.year, month.month, 20) <= today:     # the café's set, sent automatically
        it = [{"product_id": pids[5], "description": "", "quantity": 1, "unit": "gab.", "price_per_unit": 180.0}]
        plan.append({"day": month.replace(day=20), "ci": 3, "items": it, "recurring": True})
        total += gross(it)
    for days_ago, ci, it in LATE:
        d = today - dt.timedelta(days=days_ago)
        if (d.year, d.month) == (month.year, month.month):
            it = it or lines_for(ci)
            plan.append({"day": d, "ci": ci, "items": it, "late": True})
            total += gross(it)
    while total < target * 0.96 and last.day >= 1:
        d = month.replace(day=rng.randint(1, last.day))
        if d.weekday() == 6:
            continue
        ci = rng.choices([0, 1, 2, 4, 5, 6, 7], weights=[4, 2, 1, 2, 2, 1, 2])[0]
        it = lines_for(ci)
        if total + gross(it) > target * 1.08 and total > target * 0.8:
            break
        plan.append({"day": d, "ci": ci, "items": it})
        total += gross(it)
    month = nxt
    mi += 1
plan.append({"day": today - dt.timedelta(days=1), "ci": 5, "items": lines_for(5), "send": False})
plan.append({"day": today, "ci": 0, "items": [
    {"product_id": pids[0], "description": "", "quantity": 120, "unit": "gab.", "price_per_unit": 8.5},
    {"product_id": pids[1], "description": "", "quantity": 6, "unit": "st.", "price_per_unit": 35.0}]})

late = []
for p in sorted(plan, key=lambda p: p["day"]):
    doc_id = invoice(p["day"], p["ci"], p["items"], send=p.get("send", True), recurring=p.get("recurring", False))
    if p.get("late"):
        late.append(doc_id)
    elif p["day"] + dt.timedelta(days=14) < today - dt.timedelta(days=2):
        db.update_document_status(uid, doc_id, "paid")
todays = doc_id

# A credit note: two of the leather workshop's photos were reshot free of charge; the
# client paid the rest
conn = db.get_connection()
orig = conn.execute("""SELECT id, doc_date FROM documents WHERE user_id = ? AND client_id = ? AND doc_type = 'sell'
                       AND doc_date < ? ORDER BY doc_date DESC LIMIT 1""",
                    (uid, cids[7], (today - dt.timedelta(days=45)).isoformat())).fetchone()
conn.close()
if orig:
    cday = dt.date.fromisoformat(orig["doc_date"]) + dt.timedelta(days=6)
    credit_id, _ = db.create_document(uid, "credit", cids[7], cday.isoformat(),
                                      [{"product_id": pids[0], "description": "", "quantity": 2, "unit": "gab.", "price_per_unit": 8.5}],
                                      vat_rate=21.0, ref_doc_id=orig["id"], notes="Divi attēli pārfotografēti bez maksas.")
    db.log_event(uid, "document_created", document_id=credit_id, client_id=cids[7])
    db.log_email_sent(uid, credit_id, CLIENTS[7][4])
    backdate(credit_id, at(cday, 10, 12), at(cday, 10, 30))
    db.refresh_original_status(uid, orig["id"])
    db.update_document_status(uid, orig["id"], "paid")

# Offers: one waiting for an answer, one accepted
for days_ago, ci, items, status in (
        (12, 6, [{"product_id": pids[3], "description": "", "quantity": 6, "unit": "st.", "price_per_unit": 75.0}], "accepted"),
        (6, 5, [{"product_id": pids[4], "description": "", "quantity": 2, "unit": "gab.", "price_per_unit": 420.0},
                {"product_id": pids[0], "description": "", "quantity": 80, "unit": "gab.", "price_per_unit": 8.5}], None)):
    day = today - dt.timedelta(days=days_ago)
    oid, _ = db.create_document(uid, "offer", cids[ci], day.isoformat(), items, vat_rate=21.0,
                                payment_due_date=(day + dt.timedelta(days=30)).isoformat())
    backdate(oid, at(day, 9, 40))
    if status:
        db.update_document_status(uid, oid, status)

# The café's schedule itself
nxt20 = today.replace(day=20) if today.day < 20 else (today.replace(day=1) + dt.timedelta(days=32)).replace(day=20)
db.create_recurring_invoice(uid, "sell", cids[3], 21.0, "", "modern", "monthly", nxt20.isoformat(), True,
                            json.dumps([{"product_id": pids[5], "description": "", "quantity": 1, "unit": "gab.", "price_per_unit": 180.0}]),
                            payment_due_days=14)

conn = db.get_connection()
n = conn.execute("SELECT COUNT(*) FROM documents WHERE user_id = ?", (uid,)).fetchone()[0]
conn.close()
print(f"seeded paraugs (id {uid}): {n} documents; overdue {late}; today {todays}")
