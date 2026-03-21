"""
V-Rēķini — Multi-tenant SaaS Invoice Manager (FastAPI)
"""

import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

import json
import secrets
import datetime
import asyncio
import logging
import smtplib
import time
from collections import defaultdict
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
from app import registry
from app.pdf_generator import generate_invoice_pdf, TEMPLATES
from app.einvoice import generate_einvoice_xml, generate_einvoice_file

app = FastAPI(title="V-Rēķini")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

UNITS = ["kg", "gab", "kaste", "iepak.", "l", "h", "m", "m²", "m³"]


# --- Simple in-memory rate limiter ---
class RateLimiter:
    """IP-based sliding window rate limiter."""

    def __init__(self):
        self._hits = defaultdict(list)

    def is_allowed(self, key, max_requests, window_seconds):
        """Return True if the request is allowed, False if rate limited."""
        now = time.monotonic()
        hits = self._hits[key]
        # Prune old entries
        cutoff = now - window_seconds
        self._hits[key] = hits = [t for t in hits if t > cutoff]
        if len(hits) >= max_requests:
            return False
        hits.append(now)
        return True


_rate_limiter = RateLimiter()


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"

# --- Centralised email configuration ---
# Emails are sent from a single V-Rēķini address; Reply-To is set to
# the user's own email so clients can reply directly to them.
SMTP_HOST = os.getenv("SMTP_HOST", "server50.areait.lv")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "rekini@v-rekini.lv")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "V-Rēķini <rekini@v-rekini.lv>")
SMTP_SSL = os.getenv("SMTP_SSL", "true").lower() in ("true", "1", "yes")

# --- Brevo transactional email API ---
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "rekini@v-rekini.lv")
BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "V-Rēķini")

# --- Stripe ---
import stripe
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_IDS = {
    "starter_monthly": os.getenv("STRIPE_PRICE_STARTER_MONTHLY", ""),
    "starter_yearly": os.getenv("STRIPE_PRICE_STARTER_YEARLY", ""),
    "business_monthly": os.getenv("STRIPE_PRICE_BUSINESS_MONTHLY", ""),
    "business_yearly": os.getenv("STRIPE_PRICE_BUSINESS_YEARLY", ""),
}
stripe.api_key = STRIPE_SECRET_KEY


def _smtp_connect():
    """Return an authenticated SMTP connection (SSL or STARTTLS)."""
    if SMTP_SSL:
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15)
    else:
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15)
        server.starttls()
    server.login(SMTP_USER, SMTP_PASS)
    return server


def _send_email(*, to_email: str, subject: str, body: str,
                reply_to: str = "", attachment_path: str = ""):
    """Send email via Brevo API (preferred) or SMTP fallback."""
    if BREVO_API_KEY:
        return _send_via_brevo(
            to_email=to_email, subject=subject, body=body,
            reply_to=reply_to, attachment_path=attachment_path,
        )
    if SMTP_PASS:
        return _send_via_smtp(
            to_email=to_email, subject=subject, body=body,
            reply_to=reply_to, attachment_path=attachment_path,
        )
    raise RuntimeError("E-pasta serviss nav konfigurēts (nav ne BREVO_API_KEY, ne SMTP_PASS).")


def _send_via_brevo(*, to_email, subject, body, reply_to="", attachment_path=""):
    """Send email using Brevo HTTP API."""
    import httpx
    import base64

    payload = {
        "sender": {"name": BREVO_SENDER_NAME, "email": BREVO_SENDER_EMAIL},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body,
    }
    if reply_to:
        payload["replyTo"] = {"email": reply_to}

    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode()
        payload["attachment"] = [{
            "content": content_b64,
            "name": os.path.basename(attachment_path),
        }]

    resp = httpx.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "api-key": BREVO_API_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Brevo API kļūda ({resp.status_code}): {resp.text}")


def _send_via_smtp(*, to_email, subject, body, reply_to="", attachment_path=""):
    """Send email using SMTP (legacy fallback)."""
    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.attach(MIMEText(body, "plain", "utf-8"))

    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, "rb") as f:
            part = MIMEBase("application", "pdf")
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition",
                            f"attachment; filename={os.path.basename(attachment_path)}")
            msg.attach(part)

    with _smtp_connect() as server:
        server.send_message(msg)


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
    tier = user.get("tier", "free")
    return {
        "request": request,
        "current_user": user,
        "stock_enabled": _stock_enabled(user["id"]),
        "tier": tier,
        "tier_label": db.TIER_LIMITS.get(tier, {}).get("label", "Bezmaksas"),
        "tier_limits": db.get_tier_limits(tier),
        "needs_setup": not db.get_user_setting(user["id"], "company_name"),
    }


def _check_tier_feature(user, feature_key):
    """Check if user's tier has a boolean feature enabled."""
    limits = db.get_tier_limits(user.get("tier", "free"))
    return bool(limits.get(feature_key, False))


def _check_tier_limit(user, resource_type):
    """Check if user has reached their tier limit for a resource type.
    Returns (allowed: bool, current_count: int, max_count: int)."""
    limits = db.get_tier_limits(user.get("tier", "free"))
    usage = db.get_user_resource_counts(user["id"])
    key_map = {
        "documents": "max_documents",
        "clients": "max_clients",
        "products": "max_products",
    }
    max_key = key_map.get(resource_type, "max_documents")
    current = usage.get(resource_type, 0)
    maximum = limits.get(max_key, 50)
    return current < maximum, current, maximum


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

        if (path.startswith("/static") or path in ("/login", "/register", "/pricing", "/contacts", "/terms")
                or path == "/stripe/webhook" or path == "/api/registry/search"):
            return await call_next(request)

        user = _get_current_user(request)

        if not user:
            if path.startswith("/api/"):
                return JSONResponse({"error": "Unauthorized"}, status_code=401)
            return RedirectResponse("/login", status_code=303)

        if user["must_change_password"] and path != "/set-password" and path != "/logout":
            return RedirectResponse("/set-password", status_code=303)

        # Check if user needs to complete initial business setup
        setup_exempt = {"/settings", "/setup", "/logout", "/set-password"}
        if path not in setup_exempt and not path.startswith("/static") and not path.startswith("/api/") and not path.startswith("/settings/logo"):
            if not db.get_user_setting(user["id"], "company_name"):
                return RedirectResponse("/setup", status_code=303)

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

                    template = rec.get("template", "minimal")
                    filepath = generate_invoice_pdf(doc_id, template=template)

                    # Send email if enabled
                    if rec["send_email"] and (BREVO_API_KEY or SMTP_PASS):
                        client = db.get_client(rec["client_id"])
                        if client and client.get("email"):
                            settings = db.get_all_user_settings(rec["user_id"])
                            company_name = settings.get("company_name", "")
                            doc_type_name = settings.get("sell_doc_name", "Rēķins") if rec["doc_type"] == "sell" else settings.get("buy_doc_name", "Rēķins")
                            rec_user = db.get_user(rec["user_id"])
                            user_email = rec_user.get("email", "") if rec_user else ""

                            _send_email(
                                to_email=client["email"],
                                subject=f"{doc_type_name} Nr. {doc_number} — {company_name}",
                                body=f"Labdien!\n\nPielikumā nosūtām dokumentu: {doc_type_name} Nr. {doc_number}\nDatums: {today}\n\nAr cieņu,\n{company_name}\n",
                                reply_to=user_email,
                                attachment_path=filepath,
                            )

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
    db_path = db.get_db_path()
    db_exists = os.path.exists(db_path)
    db_size = os.path.getsize(db_path) if db_exists else 0
    print(f"[STARTUP] Database path: {db_path}")
    print(f"[STARTUP] Database exists: {db_exists}, size: {db_size} bytes")

    db.init_db()

    user_ct = db.user_count()
    print(f"[STARTUP] Users in database: {user_ct}")

    temp_pw = db.ensure_default_admin()
    if temp_pw:
        print(f"\n{'='*60}")
        print(f"  WARNING: Fresh database detected — no existing users found!")
        print(f"  Izveidots noklusējuma administrators:")
        print(f"  Lietotājvārds: admin")
        print(f"  Parole: {temp_pw}")
        print(f"  (Parole jāmaina pie pirmās pieslēgšanās)")
        print(f"{'='*60}\n")

    # Initialize registry DB table (data imported separately via cron)
    registry.init_registry_db()
    reg_count = registry.get_record_count()
    print(f"[STARTUP] Business registry: {reg_count} records")

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
        "page": "login",
    })


@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    # Rate limit: 10 login attempts per minute per IP
    ip = _get_client_ip(request)
    if not _rate_limiter.is_allowed(f"login:{ip}", 10, 60):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Pārāk daudz mēģinājumu. Lūdzu, uzgaidiet.",
            "username": username,
            "page": "login",
        })

    user = db.authenticate_user(username, password)
    if not user:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Nepareizs e-pasts vai parole.",
            "username": username,
            "page": "login",
        })

    if user["must_change_password"]:
        response = RedirectResponse("/set-password", status_code=303)
    else:
        response = RedirectResponse("/", status_code=303)

    return _set_session_cookie(response, user["id"])


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, error: str = "", plan: str = "", cycle: str = "monthly"):
    user = _get_current_user(request)
    if user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("register.html", {
        "request": request,
        "error": error,
        "page": "register",
        "plan": plan,
        "cycle": cycle,
        "entity_type": "business",
    })


@app.post("/register")
async def register(request: Request,
                   email: str = Form(...),
                   display_name: str = Form(""),
                   first_name: str = Form(""),
                   last_name: str = Form(""),
                   phone: str = Form(""),
                   password: str = Form(...),
                   confirm_password: str = Form(...),
                   plan: str = Form(""),
                   cycle: str = Form("monthly"),
                   entity_type: str = Form("business"),
                   reg_number: str = Form(""),
                   vat_number: str = Form(""),
                   legal_address: str = Form(""),
                   is_vat_payer: str = Form("0")):
    # Rate limit: 5 registrations per hour per IP
    ip = _get_client_ip(request)
    if not _rate_limiter.is_allowed(f"register:{ip}", 5, 3600):
        return templates.TemplateResponse("register.html", {
            "request": request, "page": "register", "plan": plan, "cycle": cycle,
            "entity_type": entity_type, "email": email,
            "error": "Pārāk daudz reģistrāciju. Lūdzu, mēģiniet vēlāk.",
        })

    # For individuals, build display_name from first + last name
    if entity_type == "individual":
        display_name = f"{first_name.strip()} {last_name.strip()}".strip()

    error_ctx = {
        "request": request, "page": "register",
        "email": email, "display_name": display_name, "phone": phone,
        "plan": plan, "cycle": cycle, "entity_type": entity_type,
        "first_name": first_name, "last_name": last_name,
        "reg_number": reg_number, "vat_number": vat_number,
        "legal_address": legal_address, "is_vat_payer": is_vat_payer,
    }

    if not display_name:
        err = "Lūdzu norādiet vārdu un uzvārdu." if entity_type == "individual" else "Lūdzu norādiet uzņēmuma nosaukumu."
        return templates.TemplateResponse("register.html", {**error_ctx, "error": err})

    if password != confirm_password:
        return templates.TemplateResponse("register.html", {**error_ctx, "error": "Paroles nesakrīt."})

    if len(password) < 6:
        return templates.TemplateResponse("register.html", {**error_ctx, "error": "Parolei jābūt vismaz 6 simbolus garai."})

    if db.get_user_by_email(email):
        return templates.TemplateResponse("register.html", {**error_ctx, "error": "E-pasts jau reģistrēts."})

    # Auto-generate username from email
    username = email.split("@")[0].lower().replace(" ", "_")
    base_username = username
    counter = 1
    while db.get_user_by_username(username):
        username = f"{base_username}{counter}"
        counter += 1

    user_id = db.create_user(
        username=username,
        password=password,
        display_name=display_name,
        email=email,
        phone=phone,
        tier="free",
    )

    # Save registration data as settings (but NOT company_name — that's set
    # during onboarding to gate the setup-complete check in middleware)
    is_business = entity_type == "business"
    db.save_all_user_settings(user_id, {
        "invoice_number_type": "type1",
        "invoice_number_separator": "-",
        "invoice_number_digits": "3",
        "default_vat_rate": "21" if (is_business and is_vat_payer == "1") else "0",
        "is_vat_payer": is_vat_payer if is_business else "0",
        "stock_enabled": "0",
        "buy_doc_prefix": "",
        "sell_doc_prefix": "",
        "buy_doc_name": "Rēķins",
        "sell_doc_name": "Rēķins",
        "default_template": "minimal",
        "entity_type": entity_type,
        "_reg_company_name": display_name,
        "reg_number": reg_number if is_business else "",
        "vat_number": vat_number if (is_business and is_vat_payer == "1") else "",
        "legal_address": legal_address if is_business else "",
    })

    # If a paid plan was selected during registration, redirect to subscription page
    if plan in ("starter", "business"):
        response = RedirectResponse(f"/pricing?upgrade={plan}&cycle={cycle}", status_code=303)
    else:
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
# Initial Setup (simplified onboarding)
# =============================================================================

@app.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request):
    user = request.state.user
    # If already set up, go to dashboard
    if db.get_user_setting(user["id"], "company_name"):
        return RedirectResponse("/", status_code=303)
    settings = db.get_all_user_settings(user["id"])
    # Use _reg_company_name from registration as the company name for pre-fill
    if not settings.get("company_name") and settings.get("_reg_company_name"):
        settings["company_name"] = settings["_reg_company_name"]
    has_logo = bool(_get_logo_path(user["id"]))
    return templates.TemplateResponse("setup.html", {
        "request": request,
        "display_name": user.get("display_name") or "",
        "settings": settings,
        "has_logo": has_logo,
    })


@app.post("/setup")
async def save_setup(
    request: Request,
    entity_type: str = Form("business"),
    company_name: str = Form(""),
    reg_number: str = Form(""),
    vat_number: str = Form(""),
    legal_address: str = Form(""),
    bank_name: str = Form(""),
    bank_account: str = Form(""),
    is_vat_payer: str = Form("0"),
    default_vat_rate: str = Form("21"),
    invoice_number_type: str = Form("type1"),
    invoice_number_separator: str = Form("-"),
    invoice_number_digits: str = Form("3"),
    electronic_doc: str = Form("0"),
    payment_due_days: str = Form(""),
):
    user = request.state.user
    settings_dict = {
        "entity_type": entity_type,
        "company_name": company_name,
        "reg_number": reg_number,
        "vat_number": vat_number,
        "legal_address": legal_address,
        "bank_name": bank_name,
        "bank_account": bank_account,
        "is_vat_payer": is_vat_payer,
        "default_vat_rate": default_vat_rate if is_vat_payer == "1" else "0",
        "invoice_number_type": invoice_number_type,
        "invoice_number_separator": invoice_number_separator,
        "invoice_number_digits": invoice_number_digits,
        "electronic_doc": electronic_doc,
        "payment_due_days": payment_due_days,
    }
    db.save_all_user_settings(user["id"], settings_dict)
    return RedirectResponse("/", status_code=303)


# =============================================================================
# Account
# =============================================================================

@app.get("/account", response_class=HTMLResponse)
async def account_page(request: Request):
    ctx = _base_context(request)
    user = request.state.user
    limits = db.get_tier_limits(user.get("tier", "free"))
    usage = db.get_user_resource_counts(user["id"])
    ctx.update({
        "page": "account",
        "limits": limits,
        "usage": usage,
        "doc_count": usage["documents"],
        "has_stripe": bool(STRIPE_SECRET_KEY),
        "tiers": db.TIER_LIMITS,
    })
    return templates.TemplateResponse("account.html", ctx)


@app.post("/account/profile")
async def update_profile(request: Request,
                         display_name: str = Form(...),
                         email: str = Form(""),
                         phone: str = Form("")):
    user = request.state.user
    db.update_user_profile(user["id"], display_name=display_name, email=email, phone=phone)
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
# Pricing (public) & Stripe billing
# =============================================================================

@app.get("/contacts", response_class=HTMLResponse)
async def contacts_page(request: Request):
    return templates.TemplateResponse("contacts.html", {
        "request": request,
        "current_user": None,
        "page": "contacts",
    })


@app.get("/terms", response_class=HTMLResponse)
async def terms_page(request: Request):
    return templates.TemplateResponse("terms.html", {
        "request": request,
        "current_user": None,
        "page": "terms",
    })


@app.get("/pricing", response_class=HTMLResponse)
async def pricing_page(request: Request, upgrade: str = "", cycle: str = "monthly"):
    user = _get_current_user(request)
    if user:
        request.state.user = user
        ctx = _base_context(request)
        limits = db.get_tier_limits(user.get("tier", "free"))
        usage = db.get_user_resource_counts(user["id"])
        ctx.update({
            "page": "pricing",
            "limits": limits,
            "usage": usage,
            "has_stripe": bool(STRIPE_SECRET_KEY),
            "upgrade": upgrade,
            "upgrade_cycle": cycle,
        })
        return templates.TemplateResponse("pricing_auth.html", ctx)
    return templates.TemplateResponse("pricing.html", {
        "request": request,
        "current_user": None,
        "page": "pricing",
    })


@app.post("/billing/checkout")
async def billing_checkout(request: Request, tier: str = Form(...), cycle: str = Form("monthly")):
    """Create a Stripe Checkout session and redirect."""
    user = request.state.user
    if tier not in ("starter", "business") or cycle not in ("monthly", "yearly"):
        return RedirectResponse("/pricing?error=invalid", status_code=303)

    price_key = f"{tier}_{cycle}"
    price_id = STRIPE_PRICE_IDS.get(price_key, "")
    if not price_id or not STRIPE_SECRET_KEY:
        return RedirectResponse("/pricing?error=stripe_not_configured", status_code=303)

    # Get or create Stripe customer
    stripe_customer_id = user.get("stripe_customer_id", "")
    if not stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.get("email", ""),
            name=user.get("display_name", user["username"]),
            metadata={"user_id": str(user["id"])},
        )
        stripe_customer_id = customer.id
        db.update_user_subscription(
            user["id"], user.get("tier", "free"),
            stripe_customer_id=stripe_customer_id,
        )

    base_url = str(request.base_url).rstrip("/")
    session = stripe.checkout.Session.create(
        customer=stripe_customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/pricing",
        metadata={"user_id": str(user["id"]), "tier": tier, "cycle": cycle},
    )
    return RedirectResponse(session.url, status_code=303)


@app.get("/billing/success", response_class=HTMLResponse)
async def billing_success(request: Request, session_id: str = ""):
    """Post-checkout success page. The webhook handles the actual activation."""
    ctx = _base_context(request)
    ctx["page"] = "billing"
    return templates.TemplateResponse("billing_success.html", ctx)


@app.post("/billing/portal")
async def billing_portal(request: Request):
    """Redirect to Stripe Customer Portal for managing subscription."""
    user = request.state.user
    stripe_customer_id = user.get("stripe_customer_id", "")
    if not stripe_customer_id or not STRIPE_SECRET_KEY:
        return RedirectResponse("/account?error=no_subscription", status_code=303)

    base_url = str(request.base_url).rstrip("/")
    session = stripe.billing_portal.Session.create(
        customer=stripe_customer_id,
        return_url=f"{base_url}/account",
    )
    return RedirectResponse(session.url, status_code=303)


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events for subscription lifecycle."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        metadata = data.get("metadata", {})
        user_id = int(metadata.get("user_id", 0))
        tier = metadata.get("tier", "starter")
        cycle = metadata.get("cycle", "monthly")
        subscription_id = data.get("subscription", "")
        customer_id = data.get("customer", "")

        if user_id:
            db.update_user_subscription(
                user_id, tier,
                billing_cycle=cycle,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                subscription_status="active",
            )
            logger.info(f"User {user_id} upgraded to {tier} ({cycle})")

    elif event_type in ("customer.subscription.updated", "customer.subscription.renewed"):
        customer_id = data.get("customer", "")
        user = db.get_user_by_stripe_customer(customer_id)
        if user:
            status = data.get("status", "")
            if status == "active":
                db.update_user_subscription(
                    user["id"], user["tier"],
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=data.get("id", ""),
                    subscription_status="active",
                )
            elif status in ("past_due", "unpaid"):
                db.update_user_subscription(
                    user["id"], user["tier"],
                    stripe_customer_id=customer_id,
                    stripe_subscription_id=data.get("id", ""),
                    subscription_status=status,
                )

    elif event_type in ("customer.subscription.deleted", "customer.subscription.canceled"):
        customer_id = data.get("customer", "")
        user = db.get_user_by_stripe_customer(customer_id)
        if user:
            db.cancel_user_subscription(user["id"])
            logger.info(f"User {user['id']} subscription cancelled, downgraded to free")

    return JSONResponse({"status": "ok"})


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


@app.post("/users/{user_id}/tier")
async def change_user_tier(request: Request, user_id: int, tier: str = Form(...)):
    user = request.state.user
    if not user["is_admin"]:
        raise HTTPException(status_code=403)
    if tier not in db.TIER_LIMITS:
        return RedirectResponse("/users?error=Nederīgs plāns", status_code=303)
    db.update_user_subscription(user_id, tier)
    target = db.get_user(user_id)
    name = target["username"] if target else str(user_id)
    label = db.TIER_LIMITS[tier]["label"]
    return RedirectResponse(f"/users?success=Lietotāja {name} plāns mainīts uz {label}", status_code=303)


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
    recent_docs = db.get_documents(uid)[:5]
    clients = db.get_all_clients(uid)
    stock = db.get_stock(uid) if stock_on else []
    stats = db.get_dashboard_stats(uid)

    ctx.update({
        "recent_docs": recent_docs,
        "clients": clients,
        "stock": stock,
        "settings": settings,
        "stats": stats,
        "einvoice_enabled": _check_tier_feature(user, "einvoice"),
        "recurring_enabled": _check_tier_feature(user, "recurring"),
        "email_enabled": user.get("tier", "free") != "free",
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
    entity_type: str = Form("business"),
    company_name: str = Form(""),
    reg_number: str = Form(""),
    vat_number: str = Form(""),
    legal_address: str = Form(""),
    bank_name: str = Form(""),
    bank_account: str = Form(""),
    use_prefixes: str = Form("0"),
    buy_doc_prefix: str = Form(""),
    sell_doc_prefix: str = Form(""),
    buy_doc_name: str = Form("Rēķins"),
    sell_doc_name: str = Form("Rēķins"),
    default_vat_rate: str = Form("21"),
    is_vat_payer: str = Form("0"),
    payment_due_days: str = Form(""),
    stock_enabled: str = Form("0"),
    electronic_doc: str = Form("0"),
    status_tracking: str = Form("0"),
    logo_width: str = Form("100"),
    default_template: str = Form("minimal"),
    invoice_number_type: str = Form("type1"),
    invoice_number_separator: str = Form(""),
    invoice_number_digits: str = Form("3"),
    email_template: str = Form(""),
):
    user = request.state.user
    settings_dict = {
        "entity_type": entity_type,
        "company_name": company_name,
        "reg_number": reg_number,
        "vat_number": vat_number if is_vat_payer == "1" else "",
        "legal_address": legal_address,
        "bank_name": bank_name,
        "bank_account": bank_account,
        "is_vat_payer": is_vat_payer,
        "use_prefixes": use_prefixes,
        "buy_doc_prefix": buy_doc_prefix,
        "sell_doc_prefix": sell_doc_prefix,
        "buy_doc_name": buy_doc_name,
        "sell_doc_name": sell_doc_name,
        "default_vat_rate": default_vat_rate if is_vat_payer == "1" else "0",
        "payment_due_days": payment_due_days,
        "stock_enabled": stock_enabled,
        "electronic_doc": electronic_doc,
        "status_tracking": status_tracking,
        "logo_width": logo_width,
        "default_template": default_template,
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
        "email_template": email_template,
    })
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
    # Support redirect back to setup/onboarding
    redirect = request.query_params.get("redirect", "/settings?saved=1")
    return RedirectResponse(redirect, status_code=303)


@app.post("/settings/logo/delete")
async def delete_logo(request: Request):
    user = request.state.user
    uid = user["id"]
    path = _get_logo_path(uid)
    if path and os.path.exists(path):
        os.remove(path)
    db.set_user_setting(uid, "logo_filename", "")
    redirect = request.query_params.get("redirect", "/settings?saved=1")
    return RedirectResponse(redirect, status_code=303)


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
    usage = db.get_user_resource_counts(user["id"])
    limits = db.get_tier_limits(user.get("tier", "free"))
    ctx.update({
        "products": products,
        "units": UNITS,
        "usage": usage,
        "limits": limits,
        "page": "products",
    })
    return templates.TemplateResponse("products.html", ctx)


@app.post("/products/add")
async def add_product(request: Request, name: str = Form(...), unit: str = Form(...)):
    user = request.state.user
    allowed, current, maximum = _check_tier_limit(user, "products")
    if not allowed:
        return RedirectResponse(f"/products?error=limit", status_code=303)
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
    usage = db.get_user_resource_counts(user["id"])
    limits = db.get_tier_limits(user.get("tier", "free"))
    ctx.update({
        "clients": clients,
        "usage": usage,
        "limits": limits,
        "page": "clients",
    })
    return templates.TemplateResponse("clients.html", ctx)


@app.post("/clients/add")
async def add_client(
    request: Request,
    name: str = Form(...),
    reg_number: str = Form(""),
    vat_number: str = Form(""),
    vat_payer: str = Form("0"),
    legal_address: str = Form(""),
    bank_name: str = Form(""),
    bank_account: str = Form(""),
    contact_person: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
):
    user = request.state.user
    if reg_number:
        existing = db.get_client_by_reg_number(user["id"], reg_number)
        if existing:
            return RedirectResponse(f"/clients?error=duplicate&name={existing['name']}", status_code=303)
    allowed, current, maximum = _check_tier_limit(user, "clients")
    if not allowed:
        return RedirectResponse(f"/clients?error=limit", status_code=303)
    db.add_client(user["id"], name, reg_number, vat_number, int(vat_payer), legal_address,
                  bank_name, bank_account, contact_person, phone, email)
    return RedirectResponse("/clients", status_code=303)


@app.post("/clients/{client_id}/edit")
async def edit_client(
    request: Request,
    client_id: int,
    name: str = Form(...),
    reg_number: str = Form(""),
    vat_number: str = Form(""),
    vat_payer: str = Form("0"),
    legal_address: str = Form(""),
    bank_name: str = Form(""),
    bank_account: str = Form(""),
    contact_person: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
):
    user = request.state.user
    db.update_client(user["id"], client_id, name=name, reg_number=reg_number,
                     vat_number=vat_number, vat_payer=int(vat_payer), legal_address=legal_address,
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
                         date_from: str = "", date_to: str = "", status: str = ""):
    ctx = _base_context(request)
    user = request.state.user
    docs = db.get_documents(
        user["id"],
        doc_type=doc_type or None,
        client_id=int(client_id) if client_id else None,
        date_from=date_from or None,
        date_to=date_to or None,
        status=status or None,
    )
    clients = db.get_all_clients(user["id"])
    settings = _user_settings(user["id"])
    usage = db.get_user_resource_counts(user["id"])
    limits = db.get_tier_limits(user.get("tier", "free"))
    ctx.update({
        "documents": docs,
        "clients": clients,
        "settings": settings,
        "usage": usage,
        "limits": limits,
        "einvoice_enabled": _check_tier_feature(user, "einvoice"),
        "recurring_enabled": _check_tier_feature(user, "recurring"),
        "email_enabled": user.get("tier", "free") != "free",
        "filters": {"doc_type": doc_type, "client_id": client_id,
                     "date_from": date_from, "date_to": date_to,
                     "status": status},
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

    # Check tier limit
    allowed, current, maximum = _check_tier_limit(user, "documents")
    if not allowed:
        return RedirectResponse(
            f"/documents?error=Dokumentu limits sasniegts ({current}/{maximum}). "
            f"<a href='/pricing'>Uzlabojiet plānu</a>, lai turpinātu.",
            status_code=303)

    form = await request.form()
    doc_type = form.get("doc_type", "buy")
    client_id = int(form.get("client_id", 0))
    doc_date = form.get("doc_date", datetime.date.today().isoformat())
    payment_due_date = form.get("payment_due_date", "")
    vat_rate = float(form.get("vat_rate", 21.0))
    notes = form.get("notes", "")
    template = form.get("template", "minimal")

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
            user["id"], doc_type, client_id, doc_date, items, vat_rate, notes,
            payment_due_date=payment_due_date,
        )
    except ValueError as e:
        return RedirectResponse(f"/documents/new?doc_type={doc_type}&error={str(e)}", status_code=303)

    try:
        generate_invoice_pdf(doc_id, template=template)
    except Exception as e:
        logger.exception("PDF generation failed for doc %s", doc_id)

    return RedirectResponse(f"/documents/{doc_id}?created=1&template={template}", status_code=303)


@app.get("/documents/{doc_id}/edit", response_class=HTMLResponse)
async def edit_document_page(request: Request, doc_id: int):
    ctx = _base_context(request)
    user = request.state.user
    uid = user["id"]
    doc, items = db.get_document(doc_id)
    if not doc or doc.get("user_id") != uid:
        raise HTTPException(status_code=404, detail="Dokuments nav atrasts")
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
        "doc_type": doc["doc_type"],
        "stock_map": stock_map,
        "templates": TEMPLATES,
        "today": datetime.date.today().isoformat(),
        "page": "documents",
        "edit_mode": True,
        "doc": doc,
        "edit_items": items,
    })
    return templates.TemplateResponse("document_form.html", ctx)


@app.post("/documents/{doc_id}/update")
async def update_document(request: Request, doc_id: int):
    user = request.state.user
    form = await request.form()
    doc_type = form.get("doc_type", "buy")
    client_id = int(form.get("client_id", 0))
    doc_date = form.get("doc_date", datetime.date.today().isoformat())
    vat_rate = float(form.get("vat_rate", 21.0))
    notes = form.get("notes", "")
    template = form.get("template", "minimal")
    payment_due_date = form.get("payment_due_date", "")

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
        return RedirectResponse(f"/documents/{doc_id}/edit?error=no_items", status_code=303)

    try:
        db.update_document(user["id"], doc_id, client_id, doc_date, items, vat_rate, notes, payment_due_date=payment_due_date)
    except ValueError as e:
        return RedirectResponse(f"/documents/{doc_id}/edit?error={str(e)}", status_code=303)

    try:
        generate_invoice_pdf(doc_id, template=template)
    except Exception as e:
        logger.exception("PDF generation failed for doc %s", doc_id)

    return RedirectResponse(f"/documents/{doc_id}?updated=1&template={template}", status_code=303)


@app.get("/documents/{doc_id}", response_class=HTMLResponse)
async def view_document(request: Request, doc_id: int, template: str = ""):
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

    if not template or template not in TEMPLATES:
        template = settings.get("default_template", "minimal")
    if template not in TEMPLATES:
        template = "minimal"

    # Build default email body for send modal
    doc_type_name = settings.get("sell_doc_name", "Rēķins") if doc["doc_type"] == "sell" else settings.get("buy_doc_name", "Rēķins")
    company_name = settings.get("company_name", "")
    raw_date = doc.get("doc_date", "")
    if raw_date and "-" in raw_date:
        dp = raw_date.split("-")
        display_date = f"{dp[2]}.{dp[1]}.{dp[0]}"
    else:
        display_date = raw_date
    custom_tpl = settings.get("email_template", "")
    if custom_tpl:
        default_email_body = custom_tpl.replace("{doc_type}", doc_type_name).replace("{doc_number}", doc["doc_number"]).replace("{date}", display_date).replace("{company}", company_name)
    else:
        default_email_body = f"Labdien!\n\nPielikumā nosūtām dokumentu: {doc_type_name} Nr. {doc['doc_number']}\nDatums: {display_date}\n\nAr cieņu,\n{company_name}\n"

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
        "default_email_body": default_email_body,
        "all_templates": _check_tier_feature(user, "all_templates"),
        "einvoice_enabled": _check_tier_feature(user, "einvoice"),
        "recurring_enabled": _check_tier_feature(user, "recurring"),
        "email_enabled": user.get("tier", "free") != "free",
        "page": "documents",
    })
    return templates.TemplateResponse("document_view.html", ctx)


@app.get("/documents/{doc_id}/pdf")
async def download_pdf(request: Request, doc_id: int, template: str = ""):
    user = request.state.user
    doc, _ = db.get_document(doc_id)
    if not doc or doc.get("user_id") != user["id"]:
        raise HTTPException(status_code=404)
    if not template or template not in TEMPLATES:
        settings = _user_settings(user["id"])
        template = settings.get("default_template", "minimal")
    if template not in TEMPLATES:
        template = "minimal"
    filepath = generate_invoice_pdf(doc_id, template=template)
    return FileResponse(filepath, media_type="application/pdf",
                        filename=os.path.basename(filepath))


@app.post("/documents/{doc_id}/send")
async def send_document_email(request: Request, doc_id: int):
    """Send invoice PDF to client via email."""
    user = request.state.user
    form = await request.form()
    recipient_email = form.get("email", "").strip()
    template = form.get("template", "minimal")

    doc, items = db.get_document(doc_id)
    if not doc or doc.get("user_id") != user["id"]:
        raise HTTPException(status_code=404)

    if not recipient_email:
        return RedirectResponse(
            f"/documents/{doc_id}?error=Nav norādīta e-pasta adrese&template={template}",
            status_code=303
        )

    if not BREVO_API_KEY and not SMTP_PASS:
        return RedirectResponse(
            f"/documents/{doc_id}?error=E-pasta serviss nav konfigurēts.&template={template}",
            status_code=303
        )

    # Check email tier limit
    limits = db.get_tier_limits(user.get("tier", "free"))
    max_emails = limits.get("max_emails_month", 0)
    if max_emails > 0:
        sent_count = db.get_emails_sent_this_month(user["id"])
        if sent_count >= max_emails:
            return RedirectResponse(
                f"/documents/{doc_id}?error=Sasniegts e-pastu limits šim mēnesim ({max_emails}).&template={template}",
                status_code=303
            )
    elif not _check_tier_feature(user, "recurring"):
        # max_emails_month == 0 and no recurring means free plan (no emails)
        # For business/admin, max_emails_month == 0 means unlimited
        if user.get("tier", "free") == "free":
            return RedirectResponse("/pricing", status_code=303)

    # Generate PDF
    filepath = generate_invoice_pdf(doc_id, template=template)

    # Get client and company info for email
    settings = _user_settings(user["id"])
    client = db.get_client(doc["client_id"])
    company_name = settings.get("company_name", "")
    doc_type_name = settings.get("sell_doc_name", "Rēķins") if doc["doc_type"] == "sell" else settings.get("buy_doc_name", "Rēķins")
    user_email = user.get("email", "")

    # Format date as dd.mm.yyyy
    raw_date = doc.get("doc_date", "")
    if raw_date and "-" in raw_date:
        dp = raw_date.split("-")
        display_date = f"{dp[2]}.{dp[1]}.{dp[0]}"
    else:
        display_date = raw_date

    # Use custom body if provided, otherwise build default
    custom_body = form.get("email_body", "").strip()
    if custom_body:
        email_body = custom_body
    else:
        default_tpl = settings.get("email_template", "")
        if default_tpl:
            email_body = default_tpl.replace("{doc_type}", doc_type_name).replace("{doc_number}", doc["doc_number"]).replace("{date}", display_date).replace("{company}", company_name)
        else:
            email_body = f"Labdien!\n\nPielikumā nosūtām dokumentu: {doc_type_name} Nr. {doc['doc_number']}\nDatums: {display_date}\n\nAr cieņu,\n{company_name}\n"

    try:
        _send_email(
            to_email=recipient_email,
            subject=f"{doc_type_name} Nr. {doc['doc_number']} — {company_name}",
            body=email_body,
            reply_to=user_email,
            attachment_path=filepath,
        )
    except Exception as e:
        return RedirectResponse(
            f"/documents/{doc_id}?error=E-pasta sūtīšanas kļūda: {str(e)}&template={template}",
            status_code=303
        )

    # Log the email send
    db.log_email_sent(user["id"], doc_id, recipient_email)

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


@app.post("/documents/{doc_id}/status")
async def toggle_document_status(request: Request, doc_id: int):
    user = request.state.user
    doc, _ = db.get_document(doc_id)
    if not doc or doc.get("user_id") != user["id"]:
        raise HTTPException(status_code=404)
    new_status = "paid" if doc.get("status", "issued") == "issued" else "issued"
    db.update_document_status(user["id"], doc_id, new_status)
    # Return JSON for AJAX requests, fall back to redirect
    accept = request.headers.get("accept", "")
    if "application/json" in accept:
        return JSONResponse({"status": new_status})
    return RedirectResponse(f"/documents/{doc_id}", status_code=303)


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
    if not _check_tier_feature(user, "recurring"):
        return RedirectResponse("/pricing", status_code=303)
    form = await request.form()

    doc_type = form.get("doc_type", "sell")
    client_id = int(form.get("client_id", 0))
    vat_rate = float(form.get("vat_rate", 21.0))
    notes = form.get("notes", "")
    template = form.get("template", "minimal")
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
    if not _check_tier_feature(user, "recurring"):
        return RedirectResponse("/pricing", status_code=303)
    form = await request.form()
    frequency = form.get("frequency", "monthly")
    send_email = form.get("send_email", "0") == "1"
    template = form.get("template", "minimal")
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
    if not _check_tier_feature(user, "recurring"):
        return RedirectResponse("/pricing", status_code=303)
    db.toggle_recurring_invoice(user["id"], recurring_id)
    return RedirectResponse("/recurring", status_code=303)


@app.post("/recurring/{recurring_id}/delete")
async def delete_recurring(request: Request, recurring_id: int):
    user = request.state.user
    if not _check_tier_feature(user, "recurring"):
        return RedirectResponse("/pricing", status_code=303)
    db.delete_recurring_invoice(user["id"], recurring_id)
    return RedirectResponse("/recurring", status_code=303)


# =============================================================================
# Export
# =============================================================================

@app.get("/export", response_class=HTMLResponse)
async def export_page(request: Request):
    ctx = _base_context(request)
    user = request.state.user
    docs = db.get_documents(user["id"])
    settings = _user_settings(user["id"])
    # Load saved accounting export presets
    raw_presets = settings.get("accounting_export_presets", "[]")
    try:
        custom_presets = json.loads(raw_presets) if raw_presets else []
    except (json.JSONDecodeError, TypeError):
        custom_presets = []
    ctx.update({
        "documents": docs,
        "templates": TEMPLATES,
        "selected_template": settings.get("default_template", "minimal"),
        "page": "export",
        "custom_presets": custom_presets,
    })
    return templates.TemplateResponse("export.html", ctx)


@app.post("/export/pdf")
async def export_pdf_bulk(
    request: Request,
    date_from: str = Form(""),
    date_to: str = Form(""),
    doc_type: str = Form(""),
    template: str = Form("minimal"),
):
    import zipfile
    import tempfile

    user = request.state.user
    docs = db.get_documents(
        user["id"],
        doc_type=doc_type or None,
        date_from=date_from or None,
        date_to=date_to or None,
    )

    if not docs:
        return RedirectResponse("/export?error=no_docs", status_code=303)

    # Create ZIP with all PDFs
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()

    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc in docs:
            filepath = generate_invoice_pdf(doc["id"], template=template)
            arcname = f"{doc['doc_number'].replace('/', '_')}.pdf"
            zf.write(filepath, arcname)

    filename = f"dokumenti_{date_from}_{date_to}.zip"
    return FileResponse(
        tmp.name,
        media_type="application/zip",
        filename=filename,
    )


# =============================================================================
# E-invoice XML Export (PEPPOL BIS Billing 3.0)
# =============================================================================

@app.get("/documents/{doc_id}/einvoice")
async def download_einvoice(request: Request, doc_id: int):
    """Download a single document as PEPPOL BIS 3.0 e-invoice XML."""
    user = request.state.user
    if not _check_tier_feature(user, "einvoice"):
        return RedirectResponse("/pricing", status_code=303)
    doc, _ = db.get_document(doc_id)
    if not doc or doc["user_id"] != user["id"]:
        raise HTTPException(status_code=404)
    filepath, filename = generate_einvoice_file(doc_id)
    return FileResponse(
        filepath,
        media_type="application/xml",
        filename=filename,
    )


@app.post("/export/einvoice")
async def export_einvoice_bulk(
    request: Request,
    date_from: str = Form(""),
    date_to: str = Form(""),
    doc_type: str = Form(""),
):
    """Export multiple documents as e-invoice XML files in a ZIP archive."""
    import zipfile
    import tempfile

    user = request.state.user
    if not _check_tier_feature(user, "einvoice"):
        return RedirectResponse("/pricing", status_code=303)
    docs = db.get_documents(
        user["id"],
        doc_type=doc_type or None,
        date_from=date_from or None,
        date_to=date_to or None,
    )

    if not docs:
        return RedirectResponse("/export?error=no_docs", status_code=303)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    tmp.close()

    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for doc in docs:
            xml_string, filename = generate_einvoice_xml(doc["id"])
            zf.writestr(filename, xml_string)

    zip_filename = f"e-rekini_{date_from}_{date_to}.zip"
    return FileResponse(
        tmp.name,
        media_type="application/zip",
        filename=zip_filename,
    )


# =============================================================================
# Accounting Export (Grāmatvedības eksports)
# =============================================================================

# Built-in presets — placeholder column configs (will be refined with real specs)
ACCOUNTING_PRESETS = {
    "horizon": {
        "name": "Horizon",
        "doc_columns": [
            {"header": "Dokumenta tips", "source": "doc_type_code"},
            {"header": "Klients.Kods", "source": "client_reg_number"},
            {"header": "PVN kategorija", "source": "vat_category"},
            {"header": "Dok. datums", "source": "doc_date", "format": "dd.mm.yyyy"},
            {"header": "Valūta.Kods", "source": "constant", "value": "EUR"},
            {"header": "Numurs", "source": "doc_number"},
            {"header": "Summa bez PVN", "source": "subtotal_no_vat"},
            {"header": "PVN summa", "source": "vat_amount"},
            {"header": "Summa ar PVN", "source": "total_with_vat"},
            {"header": "Apmaksas termiņš", "source": "payment_due_date", "format": "dd.mm.yyyy"},
            {"header": "Klients", "source": "client_name"},
            {"header": "Klients.PVN", "source": "client_vat_number"},
            {"header": "Adrese", "source": "client_address"},
            {"header": "E-pasts", "source": "client_email"},
        ],
        "item_columns": [
            {"header": "Pavadzīme.Numurs", "source": "doc_number"},
            {"header": "Nosaukums", "source": "product_name"},
            {"header": "Tips", "source": "constant", "value": "3"},
            {"header": "Daudzums", "source": "quantity"},
            {"header": "Summa", "source": "line_total"},
        ],
    },
    "jumis": {
        "name": "Jumis",
        "doc_columns": [
            {"header": "Dok.tips", "source": "doc_type_code"},
            {"header": "Numurs", "source": "doc_number"},
            {"header": "Datums", "source": "doc_date", "format": "dd.mm.yyyy"},
            {"header": "Klients", "source": "client_name"},
            {"header": "Reģ.Nr.", "source": "client_reg_number"},
            {"header": "PVN Nr.", "source": "client_vat_number"},
            {"header": "Summa bez PVN", "source": "subtotal_no_vat"},
            {"header": "PVN", "source": "vat_amount"},
            {"header": "Kopā", "source": "total_with_vat"},
            {"header": "Valūta", "source": "constant", "value": "EUR"},
        ],
        "item_columns": [
            {"header": "Dok.numurs", "source": "doc_number"},
            {"header": "Prece", "source": "product_name"},
            {"header": "Mērv.", "source": "product_unit"},
            {"header": "Daudzums", "source": "quantity"},
            {"header": "Cena", "source": "price_per_unit"},
            {"header": "Summa", "source": "line_total"},
        ],
    },
    "zalktis": {
        "name": "Zalktis",
        "doc_columns": [
            {"header": "Tips", "source": "doc_type_code"},
            {"header": "Nr.", "source": "doc_number"},
            {"header": "Datums", "source": "doc_date", "format": "dd.mm.yyyy"},
            {"header": "Partneris", "source": "client_name"},
            {"header": "Reģ.nr.", "source": "client_reg_number"},
            {"header": "PVN nr.", "source": "client_vat_number"},
            {"header": "Adrese", "source": "client_address"},
            {"header": "Bez PVN", "source": "subtotal_no_vat"},
            {"header": "PVN", "source": "vat_amount"},
            {"header": "Ar PVN", "source": "total_with_vat"},
        ],
        "item_columns": [
            {"header": "Dok.nr.", "source": "doc_number"},
            {"header": "Prece/pakalpojums", "source": "product_name"},
            {"header": "Mērvienība", "source": "product_unit"},
            {"header": "Daudzums", "source": "quantity"},
            {"header": "Cena bez PVN", "source": "price_per_unit"},
            {"header": "Summa bez PVN", "source": "line_total"},
        ],
    },
}

# All available data fields for column builder
ACCOUNTING_EXPORT_FIELDS = {
    "doc_type_code": "Dokumenta tips (Pirk./Pārd.)",
    "doc_type_name": "Dokumenta tips (nosaukums)",
    "doc_number": "Dokumenta numurs",
    "doc_date": "Datums",
    "payment_due_date": "Apmaksas datums",
    "seq_num": "Secības numurs",
    "vat_rate": "PVN likme (%)",
    "vat_category": "PVN kategorija (M/X)",
    "notes": "Piezīmes",
    "status": "Statuss",
    "subtotal_no_vat": "Summa bez PVN",
    "vat_amount": "PVN summa",
    "total_with_vat": "Summa ar PVN",
    "client_name": "Klients — nosaukums",
    "client_reg_number": "Klients — reģ. nr.",
    "client_vat_number": "Klients — PVN nr.",
    "client_address": "Klients — adrese",
    "client_bank": "Klients — banka",
    "client_account": "Klients — konts",
    "client_contact": "Klients — kontaktpersona",
    "client_phone": "Klients — telefons",
    "client_email": "Klients — e-pasts",
    "company_name": "Uzņēmums — nosaukums",
    "company_reg": "Uzņēmums — reģ. nr.",
    "company_vat": "Uzņēmums — PVN nr.",
    "company_address": "Uzņēmums — adrese",
    "company_bank": "Uzņēmums — banka",
    "company_account": "Uzņēmums — konts",
    "product_name": "Prece — nosaukums",
    "product_unit": "Prece — mērvienība",
    "quantity": "Daudzums",
    "price_per_unit": "Cena par vienību",
    "line_total": "Rindas summa",
    "constant": "Fiksēta vērtība",
}

# Fields only available in line-item sheet
_ITEM_ONLY_FIELDS = {"product_name", "product_unit", "quantity", "price_per_unit", "line_total"}


def _resolve_field_value(source, doc, item, settings, fmt=None, constant_val=""):
    """Resolve a column field value from document/item/settings data."""
    val = ""
    if source == "constant":
        val = constant_val
    elif source == "doc_type_code":
        val = "Pirk." if doc.get("doc_type") == "buy" else "Pārd."
    elif source == "doc_type_name":
        val = "Pārdošana" if doc.get("doc_type") == "sell" else "Iegāde"
    elif source == "doc_number":
        val = doc.get("doc_number", "")
    elif source == "doc_date":
        raw = doc.get("doc_date", "")
        if fmt == "dd.mm.yyyy" and raw:
            parts = raw.split("-")
            if len(parts) == 3:
                val = f"{parts[2]}.{parts[1]}.{parts[0]}"
            else:
                val = raw
        else:
            val = raw
    elif source == "payment_due_date":
        raw = doc.get("payment_due_date", "")
        if fmt == "dd.mm.yyyy" and raw:
            parts = raw.split("-")
            if len(parts) == 3:
                val = f"{parts[2]}.{parts[1]}.{parts[0]}"
            else:
                val = raw
        else:
            val = raw
    elif source == "seq_num":
        val = doc.get("seq_num", "")
    elif source == "vat_rate":
        val = doc.get("vat_rate", 21.0)
    elif source == "vat_category":
        vp = doc.get("client_vat_payer", 0)
        val = "M" if vp and str(vp) != "0" else "X"
    elif source == "notes":
        val = doc.get("notes", "") or ""
    elif source == "status":
        val = doc.get("status", "") or ""
    elif source in ("subtotal_no_vat", "vat_amount", "total_with_vat"):
        # Calculated from items
        items = doc.get("items", [])
        subtotal = sum(i["quantity"] * i["price_per_unit"] for i in items)
        vat_rate = doc.get("vat_rate", 21.0) or 21.0
        vat_amount = subtotal * (vat_rate / 100)
        if source == "subtotal_no_vat":
            val = round(subtotal, 2)
        elif source == "vat_amount":
            val = round(vat_amount, 2)
        else:
            val = round(subtotal + vat_amount, 2)
    elif source.startswith("client_"):
        val = doc.get(source, "") or ""
    elif source.startswith("company_"):
        key_map = {
            "company_name": "company_name",
            "company_reg": "reg_number",
            "company_vat": "vat_number",
            "company_address": "legal_address",
            "company_bank": "bank_name",
            "company_account": "bank_account",
        }
        val = settings.get(key_map.get(source, ""), "") or ""
    elif source == "product_name":
        val = (item or {}).get("product_name", "")
    elif source == "product_unit":
        val = (item or {}).get("product_unit", "") or (item or {}).get("unit", "")
    elif source == "quantity":
        val = (item or {}).get("quantity", "")
    elif source == "price_per_unit":
        val = (item or {}).get("price_per_unit", "")
    elif source == "line_total":
        val = (item or {}).get("total", "")
    return val


@app.post("/export/accounting")
async def export_accounting(request: Request):
    """Generate accounting Excel export with 2 sheets."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side
    import tempfile

    user = request.state.user
    if not _check_tier_feature(user, "accounting_export"):
        return RedirectResponse("/pricing", status_code=303)
    form = await request.form()
    date_from = form.get("acc_date_from", "")
    date_to = form.get("acc_date_to", "")
    doc_type = form.get("acc_doc_type", "")
    preset_key = form.get("acc_preset", "")

    settings = _user_settings(user["id"])

    # Load preset config
    if preset_key in ACCOUNTING_PRESETS:
        preset = ACCOUNTING_PRESETS[preset_key]
    elif preset_key.startswith("custom_"):
        # Load from user's saved presets
        raw = settings.get("accounting_export_presets", "[]")
        try:
            custom_presets = json.loads(raw) if raw else []
        except (json.JSONDecodeError, TypeError):
            custom_presets = []
        idx = int(preset_key.replace("custom_", ""))
        if 0 <= idx < len(custom_presets):
            preset = custom_presets[idx]
        else:
            return RedirectResponse("/export?error=no_preset", status_code=303)
    else:
        return RedirectResponse("/export?error=no_preset", status_code=303)

    docs = db.get_documents_for_export(
        user["id"],
        doc_type=doc_type or None,
        date_from=date_from or None,
        date_to=date_to or None,
    )

    if not docs:
        return RedirectResponse("/export?error=no_docs", status_code=303)

    doc_columns = preset.get("doc_columns", [])
    item_columns = preset.get("item_columns", [])

    wb = Workbook()

    # --- Sheet 1: Dokumenti (one row per document) ---
    ws_docs = wb.active
    ws_docs.title = "Dokumenti"

    header_font = Font(bold=True, size=11)
    header_alignment = Alignment(horizontal="center", wrap_text=True)
    thin_border = Border(
        bottom=Side(style="thin", color="CCCCCC"),
    )

    # Headers
    for col_idx, col_def in enumerate(doc_columns, 1):
        cell = ws_docs.cell(row=1, column=col_idx, value=col_def.get("header", ""))
        cell.font = header_font
        cell.alignment = header_alignment

    # Data rows
    for row_idx, doc in enumerate(docs, 2):
        for col_idx, col_def in enumerate(doc_columns, 1):
            val = _resolve_field_value(
                col_def.get("source", ""),
                doc, None, settings,
                fmt=col_def.get("format"),
                constant_val=col_def.get("value", ""),
            )
            cell = ws_docs.cell(row=row_idx, column=col_idx, value=val)
            cell.border = thin_border

    # Auto-width columns
    for col_idx, col_def in enumerate(doc_columns, 1):
        max_len = len(col_def.get("header", ""))
        for row in ws_docs.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
            for cell in row:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
        ws_docs.column_dimensions[ws_docs.cell(row=1, column=col_idx).column_letter].width = min(max_len + 3, 40)

    # --- Sheet 2: Pozīcijas (one row per line item) ---
    if item_columns:
        ws_items = wb.create_sheet("Pozīcijas")

        for col_idx, col_def in enumerate(item_columns, 1):
            cell = ws_items.cell(row=1, column=col_idx, value=col_def.get("header", ""))
            cell.font = header_font
            cell.alignment = header_alignment

        row_idx = 2
        for doc in docs:
            for item in doc.get("items", []):
                for col_idx, col_def in enumerate(item_columns, 1):
                    val = _resolve_field_value(
                        col_def.get("source", ""),
                        doc, item, settings,
                        fmt=col_def.get("format"),
                        constant_val=col_def.get("value", ""),
                    )
                    cell = ws_items.cell(row=row_idx, column=col_idx, value=val)
                    cell.border = thin_border
                row_idx += 1

        for col_idx, col_def in enumerate(item_columns, 1):
            max_len = len(col_def.get("header", ""))
            for row in ws_items.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
                for cell in row:
                    if cell.value:
                        max_len = max(max_len, len(str(cell.value)))
            ws_items.column_dimensions[ws_items.cell(row=1, column=col_idx).column_letter].width = min(max_len + 3, 40)

    # Save and return
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    tmp.close()
    wb.save(tmp.name)

    preset_name = preset.get("name", "eksports").lower().replace(" ", "_")
    filename = f"gramatvediba_{preset_name}_{date_from}_{date_to}.xlsx"
    return FileResponse(
        tmp.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


@app.post("/api/accounting-presets/save")
async def save_accounting_presets(request: Request):
    """Save custom accounting export presets."""
    user = request.state.user
    data = await request.json()
    presets = data.get("presets", [])
    db.set_user_setting(user["id"], "accounting_export_presets", json.dumps(presets))
    return JSONResponse({"ok": True})


@app.get("/api/accounting-presets")
async def get_accounting_presets(request: Request):
    """Get built-in and custom presets."""
    user = request.state.user
    settings = _user_settings(user["id"])
    raw = settings.get("accounting_export_presets", "[]")
    try:
        custom = json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        custom = []
    return JSONResponse({
        "builtin": {k: {"name": v["name"], "doc_columns": v["doc_columns"], "item_columns": v["item_columns"]} for k, v in ACCOUNTING_PRESETS.items()},
        "custom": custom,
        "fields": ACCOUNTING_EXPORT_FIELDS,
        "item_only_fields": list(_ITEM_ONLY_FIELDS),
    })


# =============================================================================
# API endpoints for AJAX
# =============================================================================

@app.post("/api/products/add")
async def api_add_product(request: Request):
    user = request.state.user
    allowed, current, maximum = _check_tier_limit(user, "products")
    if not allowed:
        return JSONResponse({"error": f"Produktu limits sasniegts ({current}/{maximum})"}, status_code=403)
    data = await request.json()
    product_id = db.add_product(user["id"], data["name"], data["unit"])
    product = db.get_product(product_id)
    return JSONResponse(product)


@app.post("/api/clients/add")
async def api_add_client(request: Request):
    user = request.state.user
    data = await request.json()
    reg_number = data.get("reg_number", "")
    if reg_number:
        existing = db.get_client_by_reg_number(user["id"], reg_number)
        if existing:
            return JSONResponse({"error": f"Klients ar reģ. nr. {reg_number} jau eksistē ({existing['name']})", "duplicate": True, "client": existing}, status_code=409)
    allowed, current, maximum = _check_tier_limit(user, "clients")
    if not allowed:
        return JSONResponse({"error": f"Klientu limits sasniegts ({current}/{maximum})"}, status_code=403)
    client_id = db.add_client(
        user["id"],
        name=data["name"],
        reg_number=data.get("reg_number", ""),
        vat_number=data.get("vat_number", ""),
        vat_payer=int(data.get("vat_payer", 0)),
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


# ---------- Business Registry Search ----------

@app.get("/api/registry/search")
async def api_registry_search(request: Request, q: str = ""):
    """Search the Latvian business registry by name or registration number.
    Public endpoint — registry data is already publicly available."""
    # Rate limit: 30 requests per minute per IP
    ip = _get_client_ip(request)
    if not _rate_limiter.is_allowed(f"registry:{ip}", 30, 60):
        return JSONResponse({"error": "Rate limited"}, status_code=429)
    results = registry.search(q, limit=15)
    return JSONResponse(results)


@app.get("/api/registry/status")
async def api_registry_status(request: Request):
    """Check if the business registry database is loaded."""
    user = request.state.user
    if not user or not user.get("is_admin"):
        return JSONResponse({"error": "Unauthorized"}, status_code=403)
    count = registry.get_record_count()
    return JSONResponse({"count": count, "loaded": count > 0})


# ---------- VIES VAT Number Validation ----------

@app.get("/api/vat/validate")
async def api_vat_validate(request: Request, vat_number: str = ""):
    """Validate an EU VAT number via the VIES SOAP service."""
    user = request.state.user
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    vat_number = vat_number.strip().replace(" ", "").replace("-", "")
    if len(vat_number) < 4:
        return JSONResponse({"valid": False, "error": "PVN numurs par īsu"})

    # Extract country code and number
    country_code = vat_number[:2].upper()
    number = vat_number[2:]

    # If no country prefix, assume Latvia
    if country_code.isdigit():
        country_code = "LV"
        number = vat_number

    try:
        import httpx
        soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:urn="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
    <soapenv:Body>
        <urn:checkVat>
            <urn:countryCode>{country_code}</urn:countryCode>
            <urn:vatNumber>{number}</urn:vatNumber>
        </urn:checkVat>
    </soapenv:Body>
</soapenv:Envelope>"""

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://ec.europa.eu/taxation_customs/vies/services/checkVatService",
                content=soap_body,
                headers={"Content-Type": "text/xml; charset=utf-8"},
            )

        body = resp.text
        valid = "<valid>true</valid>" in body.lower() or "<ns2:valid>true</ns2:valid>" in body.lower()

        # Extract name and address from response
        name = ""
        address = ""
        for tag in ["name", "ns2:name"]:
            start = body.find(f"<{tag}>")
            end = body.find(f"</{tag}>")
            if start != -1 and end != -1:
                name = body[start + len(tag) + 2:end].strip()
                break
        for tag in ["address", "ns2:address"]:
            start = body.find(f"<{tag}>")
            end = body.find(f"</{tag}>")
            if start != -1 and end != -1:
                address = body[start + len(tag) + 2:end].strip()
                break

        return JSONResponse({
            "valid": valid,
            "country_code": country_code,
            "vat_number": number,
            "name": name,
            "address": address,
        })

    except Exception as e:
        logger.error("VIES validation error: %s", e)
        return JSONResponse({"valid": False, "error": "VIES serviss nav pieejams"})
