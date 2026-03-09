"""
V-Rēķini — Multi-tenant SaaS Invoice Manager (FastAPI)
"""

import os
import json
import secrets
import datetime
import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from itsdangerous import URLSafeTimedSerializer

logger = logging.getLogger("vrekini")

from app import database as db
from app.pdf_generator import generate_invoice_pdf, TEMPLATES

app = FastAPI(title="V-Rēķini")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

UNITS = ["kg", "gab", "kaste", "iepak.", "l", "h", "m", "m²", "m³"]

# --- Centralised email configuration ---
# Emails are sent from a single V-Rēķini address; Reply-To is set to
# the user's own email so clients can reply directly to them.
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "rekini@v-rekini.lv")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "V-Rēķini <rekini@v-rekini.lv>")

SESSION_COOKIE = "session"
SESSION_MAX_AGE = 60 * 60 * 24 * 30  # 30 days


def _get_serializer():
    secret = db.get_setting("session_secret", "")
    if not secret:
        secret = secrets.token_urlsafe(32)
        db.set_setting("session_secret", secret)
    return URLSafeTimedSerializer(secret)


def _get_current_user(request: Request):
    cookie = request.cookies.get(SESSION_COOKIE)
    if not cookie:
        return None
    try:
        s = _get_serializer()
        user_id = s.loads(cookie, max_age=SESSION_MAX_AGE)
        return db.get_user(user_id)
    except Exception:
        return None


def _set_session_cookie(response, user_id):
    s = _get_serializer()
    token = s.dumps(user_id)
    response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_MAX_AGE,
                        httponly=True, samesite="lax")
    return response


def _stock_enabled(user_id):
    return db.get_user_setting(user_id, "stock_enabled", "0") == "1"


def _user_settings(user_id):
    return db.get_all_user_settings(user_id)


def _base_context(request):
    """Common template context for authenticated pages."""
    user = request.state.user
    return {
        "request": request,
        "current_user": user,
        "stock_enabled": _stock_enabled(user["id"]),
        "tier": user.get("tier", "free"),
        "tier_label": db.TIER_LIMITS.get(user.get("tier", "free"), {}).get("label", "Bezmaksas"),
        "needs_setup": not db.get_user_setting(user["id"], "company_name"),
    }


def _get_logo_path(user_id):
    logo_dir = os.path.join(os.path.dirname(BASE_DIR), "data", "logos")
    filename = db.get_user_setting(user_id, "logo_filename")
    if filename:
        path = os.path.join(logo_dir, filename)
        if os.path.exists(path):
            return path
    return None


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path.startswith("/static") or path in ("/login", "/register"):
            return await call_next(request)

        user = _get_current_user(request)

        if not user:
            if path.startswith("/api/"):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            return RedirectResponse("/login", status_code=303)

        if user["must_change_password"] and path != "/set-password" and path != "/logout":
            return RedirectResponse("/set-password", status_code=303)

        # Check if user needs to complete initial business setup
        setup_exempt = {"/settings", "/logout", "/set-password"}
        if path not in setup_exempt and not path.startswith("/static") and not path.startswith("/api/"):
            if not db.get_user_setting(user["id"], "company_name"):
                return RedirectResponse("/settings?setup=1", status_code=303)

        request.state.user = user
        return await call_next(request)


app.add_middleware(AuthMiddleware)


def _calc_next_run(current_date, frequency):
    """Calculate the next run date based on frequency."""
    if isinstance(current_date, str):
        current_date = datetime.date.fromisoformat(current_date)
    if frequency == "monthly":
        month = current_date.month + 1
        year = current_date.year
        if month > 12:
            month = 1
            year += 1
        day = min(current_date.day, [31,29 if year%4==0 and (year%100!=0 or year%400==0) else 28,31,30,31,30,31,31,30,31,30,31][month-1])
        return datetime.date(year, month, day)
    elif frequency == "bimonthly":
        month = current_date.month + 2
        year = current_date.year
        while month > 12:
            month -= 12
            year += 1
        day = min(current_date.day, [31,29 if year%4==0 and (year%100!=0 or year%400==0) else 28,31,30,31,30,31,31,30,31,30,31][month-1])
        return datetime.date(year, month, day)
    elif frequency == "quarterly":
        month = current_date.month + 3
        year = current_date.year
        while month > 12:
            month -= 12
            year += 1
        day = min(current_date.day, [31,29 if year%4==0 and (year%100!=0 or year%400==0) else 28,31,30,31,30,31,31,30,31,30,31][month-1])
        return datetime.date(year, month, day)
    elif frequency == "halfyearly":
        month = current_date.month + 6
        year = current_date.year
        while month > 12:
            month -= 12
            year += 1
        day = min(current_date.day, [31,29 if year%4==0 and (year%100!=0 or year%400==0) else 28,31,30,31,30,31,31,30,31,30,31][month-1])
        return datetime.date(year, month, day)
    elif frequency == "yearly":
        year = current_date.year + 1
        day = min(current_date.day, [31,29 if year%4==0 and (year%100!=0 or year%400==0) else 28,31,30,31,30,31,31,30,31,30,31][current_date.month-1])
        return datetime.date(year, current_date.month, day)
    return current_date


async def _process_recurring_invoices():
    """Background task that checks and processes due recurring invoices."""
    while True:
        try:
            today = datetime.date.today().isoformat()
            due = db.get_due_recurring_invoices(today)

            for rec in due:
                try:
                    items = json.loads(rec["items_json"])
                    if not items:
                        continue

                    doc_id, doc_number = db.create_document(
                        rec["user_id"], rec["doc_type"], rec["client_id"],
                        today, items, rec["vat_rate"], rec["notes"]
                    )

                    template = rec.get("template", "classic")
                    filepath = generate_invoice_pdf(doc_id, template=template)

                    # Send email if enabled
                    if rec["send_email"] and SMTP_PASS:
                        client = db.get_client(rec["client_id"])
                        if client and client.get("email"):
                            settings = db.get_all_user_settings(rec["user_id"])
                            company_name = settings.get("company_name", "")
                            doc_type_name = settings.get("sell_doc_name", "PAVADZĪME") if rec["doc_type"] == "sell" else settings.get("buy_doc_name", "PAVADZĪME")
                            rec_user = db.get_user(rec["user_id"])
                            user_email = rec_user.get("email", "") if rec_user else ""

                            msg = MIMEMultipart()
                            msg["From"] = SMTP_FROM
                            msg["To"] = client["email"]
                            msg["Subject"] = f"{doc_type_name} Nr. {doc_number} — {company_name}"
                            if user_email:
                                msg["Reply-To"] = user_email

                            body = f"Labdien!\n\nPielikumā nosūtām dokumentu: {doc_type_name} Nr. {doc_number}\nDatums: {today}\n\nAr cieņu,\n{company_name}\n"
                            msg.attach(MIMEText(body, "plain", "utf-8"))

                            with open(filepath, "rb") as f:
                                part = MIMEBase("application", "pdf")
                                part.set_payload(f.read())
                                encoders.encode_base64(part)
                                part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(filepath)}")
                                msg.attach(part)

                            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                                server.starttls()
                                server.login(SMTP_USER, SMTP_PASS)
                                server.send_message(msg)

                    # Calculate next run
                    next_run = _calc_next_run(rec["next_run"], rec["frequency"])
                    db.update_recurring_next_run(rec["id"], next_run.isoformat())
                    logger.info(f"Recurring #{rec['id']}: created doc #{doc_id}, next run {next_run}")

                except Exception as e:
                    logger.error(f"Error processing recurring invoice #{rec['id']}: {e}")

        except Exception as e:
            logger.error(f"Error in recurring invoice loop: {e}")

        await asyncio.sleep(3600)  # Check every hour


@app.on_event("startup")
async def startup():
    db.init_db()
    temp_pw = db.ensure_default_admin()
    if temp_pw:
        print(f"\n{'='*60}")
        print(f"  Izveidots noklusējuma administrators:")
        print(f"  Lietotājvārds: admin")
        print(f"  Parole: {temp_pw}")
        print(f"  (Parole jāmaina pie pirmās pieslēgšanās)")
        print(f"{'='*60}\n")

    # Start recurring invoice background task
    asyncio.create_task(_process_recurring_invoices())


# =============================================================================
# Auth routes
# =============================================================================

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = "", message: str = ""):
    user = _get_current_user(request)
    if user and not user["must_change_password"]:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": error,
        "message": message,
    })


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    user = db.authenticate_user(username, password)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Nepareizs lietotājvārds vai parole.",
            "username": username,
        })

    if user["must_change_password"]:
        response = RedirectResponse("/set-password", status_code=303)
    else:
        response = RedirectResponse("/", status_code=303)

    return _set_session_cookie(response, user["id"])


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = ""):
    user = _get_current_user(request)
    if user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("register.html", {
        "request": request,
        "error": error,
    })


@app.post("/register")
async def register(request: Request,
                   username: str = Form(...),
                   email: str = Form(...),
                   display_name: str = Form(...),
                   password: str = Form(...),
                   confirm_password: str = Form(...)):
    if password != confirm_password:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Paroles nesakrīt.",
            "username": username, "email": email, "display_name": display_name,
        })

    if len(password) < 6:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Parolei jābūt vismaz 6 simbolus garai.",
            "username": username, "email": email, "display_name": display_name,
        })

    if db.get_user_by_username(username):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "Lietotājvārds jau aizņemts.",
            "username": username, "email": email, "display_name": display_name,
        })

    if email and db.get_user_by_email(email):
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": "E-pasts jau reģistrēts.",
            "username": username, "email": email, "display_name": display_name,
        })

    user_id = db.create_user(
        username=username,
        password=password,
        display_name=display_name,
        email=email,
        tier="free",
    )

    # Set default settings for new user
    db.save_all_user_settings(user_id, {
        "invoice_number_type": "type1",
        "invoice_number_separator": "-",
        "invoice_number_digits": "3",
        "default_vat_rate": "21",
        "stock_enabled": "0",
        "buy_doc_prefix": "PIR",
        "sell_doc_prefix": "PAR",
        "buy_doc_name": "PIRKUMA PAVADZĪME",
        "sell_doc_name": "PĀRDOŠANAS PAVADZĪME",
    })

    response = RedirectResponse("/", status_code=303)
    return _set_session_cookie(response, user_id)


@app.get("/set-password", response_class=HTMLResponse)
async def set_password_page(request: Request, error: str = ""):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    return templates.TemplateResponse("set_password.html", {
        "request": request,
        "display_name": user["display_name"] or user["username"],
        "error": error,
    })


@app.post("/set-password")
async def set_password(request: Request,
                       new_password: str = Form(...),
                       confirm_password: str = Form(...)):
    user = _get_current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)

    if new_password != confirm_password:
        return templates.TemplateResponse("set_password.html", {
            "request": request,
            "display_name": user["display_name"] or user["username"],
            "error": "Paroles nesakrīt.",
        })

    if len(new_password) < 6:
        return templates.TemplateResponse("set_password.html", {
            "request": request,
            "display_name": user["display_name"] or user["username"],
            "error": "Parolei jābūt vismaz 6 simbolus garai.",
        })

    db.update_user_password(user["id"], new_password)
    response = RedirectResponse("/", status_code=303)
    return _set_session_cookie(response, user["id"])


@app.get("/logout")
async def logout(request: Request):
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


# =============================================================================
# Account
# =============================================================================

@app.get("/account", response_class=HTMLResponse)
async def account_page(request: Request):
    ctx = _base_context(request)
    user = request.state.user
    limits = db.get_tier_limits(user.get("tier", "free"))
    doc_count = db.get_user_document_count(user["id"])
    ctx.update({
        "page": "account",
        "limits": limits,
        "doc_count": doc_count,
    })
    return templates.TemplateResponse("account.html", ctx)


@app.post("/account/profile")
async def update_profile(request: Request,
                         display_name: str = Form(...),
                         email: str = Form("")):
    user = request.state.user
    db.update_user_profile(user["id"], display_name=display_name, email=email)
    return RedirectResponse("/account?saved=profile", status_code=303)


@app.post("/account/password")
async def change_password(request: Request,
                          current_password: str = Form(...),
                          new_password: str = Form(...),
                          confirm_password: str = Form(...)):
    user = request.state.user

    if not db.authenticate_user(user["username"], current_password):
        return RedirectResponse("/account?error=wrong_password", status_code=303)

    if new_password != confirm_password:
        return RedirectResponse("/account?error=mismatch", status_code=303)

    if len(new_password) < 6:
        return RedirectResponse("/account?error=too_short", status_code=303)

    db.update_user_password(user["id"], new_password)
    return RedirectResponse("/account?saved=password", status_code=303)


# =============================================================================
# User management (admin only)
# =============================================================================

@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request, error: str = "", success: str = ""):
    ctx = _base_context(request)
    user = request.state.user
    users = db.get_all_users() if user["is_admin"] else []
    ctx.update({
        "users": users,
        "error": error,
        "success": success,
        "page": "users",
        "tiers": db.TIER_LIMITS,
    })
    return templates.TemplateResponse("users.html", ctx)


@app.post("/users/add")
async def add_user(request: Request,
                   username: str = Form(...),
                   display_name: str = Form(...),
                   password: str = Form(...),
                   email: str = Form("")):
    user = request.state.user
    if not user["is_admin"]:
        raise HTTPException(status_code=403)

    if db.get_user_by_username(username):
        return RedirectResponse("/users?error=Lietotājvārds jau aizņemts", status_code=303)

    if len(password) < 6:
        return RedirectResponse("/users?error=Parolei jābūt vismaz 6 simbolus garai", status_code=303)

    new_user_id = db.create_user(username, password, display_name, email=email,
                                 must_change_password=True)

    # Set default settings
    db.save_all_user_settings(new_user_id, {
        "invoice_number_type": "type1",
        "invoice_number_separator": "-",
        "invoice_number_digits": "3",
        "default_vat_rate": "21",
        "stock_enabled": "0",
    })

    return RedirectResponse("/users?success=Lietotājs izveidots", status_code=303)


@app.post("/users/{user_id}/delete")
async def delete_user(request: Request, user_id: int):
    user = request.state.user
    if not user["is_admin"]:
        raise HTTPException(status_code=403)
    if user_id == user["id"]:
        return RedirectResponse("/users?error=Nevar dzēst sevi", status_code=303)
    db.delete_user(user_id)
    return RedirectResponse("/users?success=Lietotājs dzēsts", status_code=303)


# =============================================================================
# Dashboard
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    ctx = _base_context(request)
    user = request.state.user
    uid = user["id"]
    settings = _user_settings(uid)
    stock_on = _stock_enabled(uid)
    recent_docs = db.get_documents(uid)[:10]
    stock = db.get_stock(uid) if stock_on else []
    stats = db.get_dashboard_stats(uid)

    ctx.update({
        "recent_docs": recent_docs,
        "stock": stock,
        "settings": settings,
        "stats": stats,
        "page": "dashboard",
    })
    return templates.TemplateResponse("dashboard.html", ctx)


# =============================================================================
# Settings (per-user)
# =============================================================================

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    ctx = _base_context(request)
    user = request.state.user
    settings = _user_settings(user["id"])
    ctx.update({
        "settings": settings,
        "page": "settings",
        "has_logo": _get_logo_path(user["id"]) is not None,
    })
    return templates.TemplateResponse("settings.html", ctx)


@app.post("/settings")
async def save_settings(
    request: Request,
    company_name: str = Form(""),
    reg_number: str = Form(""),
    vat_number: str = Form(""),
    legal_address: str = Form(""),
    bank_name: str = Form(""),
    bank_account: str = Form(""),
    buy_doc_prefix: str = Form("PIR"),
    sell_doc_prefix: str = Form("PAR"),
    buy_doc_name: str = Form("PIRKUMA PAVADZĪME"),
    sell_doc_name: str = Form("PĀRDOŠANAS PAVADZĪME"),
    default_vat_rate: str = Form("21"),
    stock_enabled: str = Form("0"),
    invoice_number_type: str = Form("type1"),
    invoice_number_separator: str = Form("-"),
    invoice_number_digits: str = Form("3"),
):
    user = request.state.user
    settings_dict = {
        "company_name": company_name,
        "reg_number": reg_number,
        "vat_number": vat_number,
        "legal_address": legal_address,
        "bank_name": bank_name,
        "bank_account": bank_account,
        "buy_doc_prefix": buy_doc_prefix,
        "sell_doc_prefix": sell_doc_prefix,
        "buy_doc_name": buy_doc_name,
        "sell_doc_name": sell_doc_name,
        "default_vat_rate": default_vat_rate,
        "stock_enabled": stock_enabled,
    }

    # When stock is first enabled, record the date so stock counts from 0
    if stock_enabled == "1":
        existing = db.get_user_setting(user["id"], "stock_enabled_date", "")
        if not existing:
            settings_dict["stock_enabled_date"] = datetime.date.today().isoformat()
    else:
        # If stock is disabled, clear the enabled date so re-enabling resets again
        settings_dict["stock_enabled_date"] = ""

    settings_dict.update({
        "invoice_number_type": invoice_number_type,
        "invoice_number_separator": invoice_number_separator,
        "invoice_number_digits": invoice_number_digits,
    }
    db.save_all_user_settings(user["id"], settings_dict)
    return RedirectResponse("/settings?saved=1", status_code=303)


@app.post("/settings/logo")
async def upload_logo(request: Request, logo: UploadFile = File(...)):
    user = request.state.user
    uid = user["id"]
    allowed = {".png", ".jpg", ".jpeg", ".gif"}
    ext = os.path.splitext(logo.filename or "")[1].lower()
    if ext not in allowed:
        return RedirectResponse("/settings?error=logo_type", status_code=303)

    logo_dir = os.path.join(os.path.dirname(BASE_DIR), "data", "logos")
    os.makedirs(logo_dir, exist_ok=True)

    # Remove old logo
    old_path = _get_logo_path(uid)
    if old_path and os.path.exists(old_path):
        os.remove(old_path)

    filename = f"{uid}_logo{ext}"
    filepath = os.path.join(logo_dir, filename)
    content = await logo.read()
    with open(filepath, "wb") as f:
        f.write(content)

    db.set_user_setting(uid, "logo_filename", filename)
    return RedirectResponse("/settings?saved=1", status_code=303)


@app.post("/settings/logo/delete")
async def delete_logo(request: Request):
    user = request.state.user
    uid = user["id"]
    path = _get_logo_path(uid)
    if path and os.path.exists(path):
        os.remove(path)
    db.set_user_setting(uid, "logo_filename", "")
    return RedirectResponse("/settings?saved=1", status_code=303)


@app.get("/api/logo")
async def get_user_logo(request: Request):
    user = request.state.user
    path = _get_logo_path(user["id"])
    if path:
        return FileResponse(path)
    raise HTTPException(404)


# =============================================================================
# Products (per-user)
# =============================================================================

@app.get("/products", response_class=HTMLResponse)
async def products_page(request: Request):
    ctx = _base_context(request)
    user = request.state.user
    products = db.get_all_products(user["id"])
    ctx.update({
        "products": products,
        "units": UNITS,
        "page": "products",
    })
    return templates.TemplateResponse("products.html", ctx)


@app.post("/products/add")
async def add_product(request: Request, name: str = Form(...), unit: str = Form(...)):
    user = request.state.user
    db.add_product(user["id"], name, unit)
    return RedirectResponse("/products", status_code=303)


@app.post("/products/{product_id}/edit")
async def edit_product(request: Request, product_id: int,
                       name: str = Form(...), unit: str = Form(...)):
    user = request.state.user
    db.update_product(user["id"], product_id, name, unit)
    return RedirectResponse("/products", status_code=303)


@app.post("/products/{product_id}/delete")
async def delete_product(request: Request, product_id: int):
    user = request.state.user
    db.delete_product(user["id"], product_id)
    return RedirectResponse("/products", status_code=303)


# =============================================================================
# Clients (per-user)
# =============================================================================

@app.get("/clients", response_class=HTMLResponse)
async def clients_page(request: Request):
    ctx = _base_context(request)
    user = request.state.user
    clients = db.get_all_clients(user["id"])
    ctx.update({
        "clients": clients,
        "page": "clients",
    })
    return templates.TemplateResponse("clients.html", ctx)


@app.post("/clients/add")
async def add_client(
    request: Request,
    name: str = Form(...),
    reg_number: str = Form(""),
    vat_number: str = Form(""),
    legal_address: str = Form(""),
    bank_name: str = Form(""),
    bank_account: str = Form(""),
    contact_person: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
):
    user = request.state.user
    db.add_client(user["id"], name, reg_number, vat_number, legal_address,
                  bank_name, bank_account, contact_person, phone, email)
    return RedirectResponse("/clients", status_code=303)


@app.post("/clients/{client_id}/edit")
async def edit_client(
    request: Request,
    client_id: int,
    name: str = Form(...),
    reg_number: str = Form(""),
    vat_number: str = Form(""),
    legal_address: str = Form(""),
    bank_name: str = Form(""),
    bank_account: str = Form(""),
    contact_person: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
):
    user = request.state.user
    db.update_client(user["id"], client_id, name=name, reg_number=reg_number,
                     vat_number=vat_number, legal_address=legal_address,
                     bank_name=bank_name, bank_account=bank_account,
                     contact_person=contact_person, phone=phone, email=email)
    return RedirectResponse("/clients", status_code=303)


@app.post("/clients/{client_id}/delete")
async def delete_client(request: Request, client_id: int):
    user = request.state.user
    db.delete_client(user["id"], client_id)
    return RedirectResponse("/clients", status_code=303)


# =============================================================================
# Documents (per-user)
# =============================================================================

@app.get("/documents", response_class=HTMLResponse)
async def documents_page(request: Request, doc_type: str = "", client_id: str = "",
                         date_from: str = "", date_to: str = ""):
    ctx = _base_context(request)
    user = request.state.user
    docs = db.get_documents(
        user["id"],
        doc_type=doc_type or None,
        client_id=int(client_id) if client_id else None,
        date_from=date_from or None,
        date_to=date_to or None,
    )
    clients = db.get_all_clients(user["id"])
    ctx.update({
        "documents": docs,
        "clients": clients,
        "filters": {"doc_type": doc_type, "client_id": client_id,
                     "date_from": date_from, "date_to": date_to},
        "page": "documents",
    })
    return templates.TemplateResponse("documents.html", ctx)


@app.get("/documents/new", response_class=HTMLResponse)
async def new_document_page(request: Request, doc_type: str = "buy"):
    ctx = _base_context(request)
    user = request.state.user
    uid = user["id"]
    clients = db.get_all_clients(uid)
    products = db.get_all_products(uid)
    settings = _user_settings(uid)
    stock_on = _stock_enabled(uid)
    stock_data = db.get_stock(uid) if stock_on else []
    stock_map = {s["id"]: s["stock"] for s in stock_data}
    ctx.update({
        "clients": clients,
        "products": products,
        "units": UNITS,
        "settings": settings,
        "doc_type": doc_type,
        "stock_map": stock_map,
        "templates": TEMPLATES,
        "today": datetime.date.today().isoformat(),
        "page": "new_document",
    })
    return templates.TemplateResponse("document_form.html", ctx)


@app.post("/documents/create")
async def create_document(request: Request):
    user = request.state.user
    form = await request.form()
    doc_type = form.get("doc_type", "buy")
    client_id = int(form.get("client_id", 0))
    doc_date = form.get("doc_date", datetime.date.today().isoformat())
    vat_rate = float(form.get("vat_rate", 21.0))
    notes = form.get("notes", "")
    template = form.get("template", "classic")

    items = []
    i = 0
    while f"items[{i}][product_id]" in form:
        product_id = int(form[f"items[{i}][product_id]"])
        quantity = float(form[f"items[{i}][quantity]"])
        unit = form[f"items[{i}][unit]"]
        price_per_unit = float(form[f"items[{i}][price_per_unit]"])
        items.append({
            "product_id": product_id,
            "quantity": quantity,
            "unit": unit,
            "price_per_unit": price_per_unit,
        })
        i += 1

    if not items:
        return RedirectResponse(f"/documents/new?doc_type={doc_type}&error=no_items", status_code=303)

    try:
        doc_id, doc_number = db.create_document(
            user["id"], doc_type, client_id, doc_date, items, vat_rate, notes
        )
    except ValueError as e:
        return RedirectResponse(f"/documents/new?doc_type={doc_type}&error={str(e)}", status_code=303)

    try:
        generate_invoice_pdf(doc_id, template=template)
    except Exception as e:
        logger.exception("PDF generation failed for doc %s", doc_id)

    return RedirectResponse(f"/documents/{doc_id}?created=1", status_code=303)


@app.get("/documents/{doc_id}", response_class=HTMLResponse)
async def view_document(request: Request, doc_id: int, template: str = "classic"):
    ctx = _base_context(request)
    user = request.state.user
    doc, items = db.get_document(doc_id)
    if not doc or doc.get("user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Dokuments nav atrasts")
    client = db.get_client(doc["client_id"])
    settings = _user_settings(user["id"])

    subtotal = sum(item["quantity"] * item["price_per_unit"] for item in items)
    vat_amount = subtotal * (doc["vat_rate"] / 100)
    total = subtotal + vat_amount

    if template not in TEMPLATES:
        template = "classic"

    ctx.update({
        "doc": doc,
        "items": items,
        "client": client,
        "settings": settings,
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "total": total,
        "templates": TEMPLATES,
        "selected_template": template,
        "has_logo": _get_logo_path(user["id"]) is not None,
        "page": "documents",
    })
    return templates.TemplateResponse("document_view.html", ctx)


@app.get("/documents/{doc_id}/pdf")
async def download_pdf(request: Request, doc_id: int, template: str = "classic"):
    user = request.state.user
    doc, _ = db.get_document(doc_id)
    if not doc or doc.get("user_id") != user["id"]:
        raise HTTPException(status_code=404)
    filepath = generate_invoice_pdf(doc_id, template=template)
    return FileResponse(filepath, media_type="application/pdf",
                        filename=os.path.basename(filepath))


@app.post("/documents/{doc_id}/send")
async def send_document_email(request: Request, doc_id: int):
    """Send invoice PDF to client via email."""
    user = request.state.user
    form = await request.form()
    recipient_email = form.get("email", "").strip()
    template = form.get("template", "classic")

    doc, items = db.get_document(doc_id)
    if not doc or doc.get("user_id") != user["id"]:
        raise HTTPException(status_code=404)

    if not recipient_email:
        return RedirectResponse(
            f"/documents/{doc_id}?error=Nav norādīta e-pasta adrese&template={template}",
            status_code=303
        )

    if not SMTP_PASS:
        return RedirectResponse(
            f"/documents/{doc_id}?error=E-pasta serviss nav konfigurēts.&template={template}",
            status_code=303
        )

    # Generate PDF
    filepath = generate_invoice_pdf(doc_id, template=template)

    # Get client and company info for email
    settings = _user_settings(user["id"])
    client = db.get_client(doc["client_id"])
    company_name = settings.get("company_name", "")
    doc_type_name = settings.get("sell_doc_name", "PAVADZĪME") if doc["doc_type"] == "sell" else settings.get("buy_doc_name", "PAVADZĪME")
    user_email = user.get("email", "")

    # Build email — sent from central V-Rēķini address, Reply-To is the user
    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM
    msg["To"] = recipient_email
    msg["Subject"] = f"{doc_type_name} Nr. {doc['doc_number']} — {company_name}"
    if user_email:
        msg["Reply-To"] = user_email

    body = f"""Labdien!

Pielikumā nosūtām dokumentu: {doc_type_name} Nr. {doc['doc_number']}
Datums: {doc['doc_date']}

Ar cieņu,
{company_name}
"""
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # Attach PDF
    with open(filepath, "rb") as f:
        part = MIMEBase("application", "pdf")
        part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(filepath)}")
        msg.attach(part)

    # Send via centralised SMTP
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
    except Exception as e:
        return RedirectResponse(
            f"/documents/{doc_id}?error=E-pasta sūtīšanas kļūda: {str(e)}&template={template}",
            status_code=303
        )

    # Save the email as client's email if not already set
    if client and not client.get("email"):
        db.update_client(user["id"], client["id"], email=recipient_email)

    return RedirectResponse(
        f"/documents/{doc_id}?sent=1&template={template}",
        status_code=303
    )


@app.post("/documents/{doc_id}/delete")
async def delete_document(request: Request, doc_id: int):
    user = request.state.user
    db.delete_document(user["id"], doc_id)
    return RedirectResponse("/documents", status_code=303)


# =============================================================================
# Stock (per-user)
# =============================================================================

@app.get("/stock", response_class=HTMLResponse)
async def stock_page(request: Request, date_from: str = "", date_to: str = ""):
    ctx = _base_context(request)
    user = request.state.user
    stock_on = _stock_enabled(user["id"])
    stock = db.get_stock(user["id"], date_from=date_from or None,
                         date_to=date_to or None) if stock_on else []
    ctx.update({
        "stock": stock,
        "filters": {"date_from": date_from, "date_to": date_to},
        "page": "stock",
    })
    return templates.TemplateResponse("stock.html", ctx)


# =============================================================================
# Recurring Invoices
# =============================================================================

FREQUENCY_LABELS = {
    "monthly": "Katru mēnesi",
    "bimonthly": "Katrus 2 mēnešus",
    "quarterly": "Katru ceturksni",
    "halfyearly": "Katrus 6 mēnešus",
    "yearly": "Katru gadu",
}


@app.get("/recurring", response_class=HTMLResponse)
async def recurring_page(request: Request):
    ctx = _base_context(request)
    user = request.state.user
    recurring = db.get_recurring_invoices(user["id"])
    ctx.update({
        "recurring": recurring,
        "frequency_labels": FREQUENCY_LABELS,
        "page": "recurring",
    })
    return templates.TemplateResponse("recurring.html", ctx)


@app.post("/recurring/create")
async def create_recurring(request: Request):
    user = request.state.user
    form = await request.form()

    doc_type = form.get("doc_type", "sell")
    client_id = int(form.get("client_id", 0))
    vat_rate = float(form.get("vat_rate", 21.0))
    notes = form.get("notes", "")
    template = form.get("template", "classic")
    frequency = form.get("frequency", "monthly")
    next_run = form.get("next_run", "")
    send_email = form.get("send_email", "0") == "1"

    if not next_run:
        next_run = _calc_next_run(datetime.date.today(), frequency).isoformat()

    # Collect items from form
    items = []
    i = 0
    while f"items[{i}][product_id]" in form:
        items.append({
            "product_id": int(form[f"items[{i}][product_id]"]),
            "quantity": float(form[f"items[{i}][quantity]"]),
            "unit": form[f"items[{i}][unit]"],
            "price_per_unit": float(form[f"items[{i}][price_per_unit]"]),
        })
        i += 1

    if not items:
        return RedirectResponse("/recurring?error=no_items", status_code=303)

    db.create_recurring_invoice(
        user["id"], doc_type, client_id, vat_rate, notes, template,
        frequency, next_run, send_email, json.dumps(items)
    )

    return RedirectResponse("/recurring?created=1", status_code=303)


@app.post("/recurring/from-document/{doc_id}")
async def create_recurring_from_document(request: Request, doc_id: int):
    """Create a recurring invoice schedule from an existing document."""
    user = request.state.user
    form = await request.form()
    frequency = form.get("frequency", "monthly")
    send_email = form.get("send_email", "0") == "1"
    template = form.get("template", "classic")
    next_run = form.get("next_run", "")

    doc, items = db.get_document(doc_id)
    if not doc or doc.get("user_id") != user["id"]:
        raise HTTPException(status_code=404)

    if not next_run:
        next_run = _calc_next_run(datetime.date.today(), frequency).isoformat()

    items_data = [
        {
            "product_id": item["product_id"],
            "quantity": item["quantity"],
            "unit": item["unit"],
            "price_per_unit": item["price_per_unit"],
        }
        for item in items
    ]

    db.create_recurring_invoice(
        user["id"], doc["doc_type"], doc["client_id"], doc["vat_rate"],
        doc.get("notes", ""), template, frequency, next_run, send_email,
        json.dumps(items_data)
    )

    return RedirectResponse(f"/documents/{doc_id}?scheduled=1&template={template}", status_code=303)


@app.post("/recurring/{recurring_id}/toggle")
async def toggle_recurring(request: Request, recurring_id: int):
    user = request.state.user
    db.toggle_recurring_invoice(user["id"], recurring_id)
    return RedirectResponse("/recurring", status_code=303)


@app.post("/recurring/{recurring_id}/delete")
async def delete_recurring(request: Request, recurring_id: int):
    user = request.state.user
    db.delete_recurring_invoice(user["id"], recurring_id)
    return RedirectResponse("/recurring", status_code=303)


# =============================================================================
# API endpoints for AJAX
# =============================================================================

@app.post("/api/products/add")
async def api_add_product(request: Request):
    user = request.state.user
    data = await request.json()
    product_id = db.add_product(user["id"], data["name"], data["unit"])
    product = db.get_product(product_id)
    return JSONResponse(product)


@app.post("/api/clients/add")
async def api_add_client(request: Request):
    user = request.state.user
    data = await request.json()
    client_id = db.add_client(
        user["id"],
        name=data["name"],
        reg_number=data.get("reg_number", ""),
        vat_number=data.get("vat_number", ""),
        legal_address=data.get("legal_address", ""),
        bank_name=data.get("bank_name", ""),
        bank_account=data.get("bank_account", ""),
    )
    client = db.get_client(client_id)
    return JSONResponse(client)


@app.get("/api/stock/{product_id}")
async def api_product_stock(request: Request, product_id: int):
    user = request.state.user
    stock = db.get_product_stock(user["id"], product_id)
    return JSONResponse({"stock": stock})


@app.get("/api/invoice-preview")
async def api_invoice_preview(request: Request,
                              number_type: str = "type1",
                              separator: str = "-",
                              digits: str = "3"):
    """Preview what invoice numbers will look like."""
    today = datetime.date.today()
    year_short = today.year % 100
    min_digits = int(digits) if digits.isdigit() else 3

    if number_type == "type1":
        example = f"{year_short}{separator}{'1'.zfill(min_digits)}"
        example2 = f"{year_short}{separator}{'42'.zfill(min_digits)}"
    elif number_type == "type2":
        day = today.day
        month = today.month
        example = f"01/{day:02d}-{month:02d}"
        example2 = f"05/{day:02d}-{month:02d}"
    else:
        example = "1".zfill(min_digits)
        example2 = "42".zfill(min_digits)

    return JSONResponse({"example1": example, "example2": example2})
