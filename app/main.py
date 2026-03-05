"""
Pavadzīmju Pārvaldnieks — Web Application (FastAPI)
Main application entry point with all routes.
"""

import os
import datetime
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import database as db
from app.pdf_generator import generate_invoice_pdf, TEMPLATES

app = FastAPI(title="Pavadzīmju Pārvaldnieks")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

UNITS = ["kg", "gab", "kaste", "iepak.", "l"]


@app.on_event("startup")
def startup():
    db.init_db()


# =============================================================================
# Dashboard
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    recent_docs = db.get_documents()[:10]
    stock = db.get_stock()
    settings = db.get_all_settings()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "recent_docs": recent_docs,
        "stock": stock,
        "settings": settings,
        "page": "dashboard",
    })


# =============================================================================
# Settings
# =============================================================================

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    settings = db.get_all_settings()
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": settings,
        "page": "settings",
    })


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
):
    db.save_all_settings({
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
    })
    return RedirectResponse("/settings?saved=1", status_code=303)


# =============================================================================
# Products
# =============================================================================

@app.get("/products", response_class=HTMLResponse)
async def products_page(request: Request):
    products = db.get_all_products()
    return templates.TemplateResponse("products.html", {
        "request": request,
        "products": products,
        "units": UNITS,
        "page": "products",
    })


@app.post("/products/add")
async def add_product(name: str = Form(...), unit: str = Form(...)):
    db.add_product(name, unit)
    return RedirectResponse("/products", status_code=303)


@app.post("/products/{product_id}/edit")
async def edit_product(product_id: int, name: str = Form(...), unit: str = Form(...)):
    db.update_product(product_id, name, unit)
    return RedirectResponse("/products", status_code=303)


@app.post("/products/{product_id}/delete")
async def delete_product(product_id: int):
    db.delete_product(product_id)
    return RedirectResponse("/products", status_code=303)


# =============================================================================
# Clients
# =============================================================================

@app.get("/clients", response_class=HTMLResponse)
async def clients_page(request: Request):
    clients = db.get_all_clients()
    return templates.TemplateResponse("clients.html", {
        "request": request,
        "clients": clients,
        "page": "clients",
    })


@app.post("/clients/add")
async def add_client(
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
    db.add_client(name, reg_number, vat_number, legal_address,
                  bank_name, bank_account, contact_person, phone, email)
    return RedirectResponse("/clients", status_code=303)


@app.post("/clients/{client_id}/edit")
async def edit_client(
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
    db.update_client(client_id, name=name, reg_number=reg_number, vat_number=vat_number,
                     legal_address=legal_address, bank_name=bank_name, bank_account=bank_account,
                     contact_person=contact_person, phone=phone, email=email)
    return RedirectResponse("/clients", status_code=303)


@app.post("/clients/{client_id}/delete")
async def delete_client(client_id: int):
    db.delete_client(client_id)
    return RedirectResponse("/clients", status_code=303)


# =============================================================================
# Documents
# =============================================================================

@app.get("/documents", response_class=HTMLResponse)
async def documents_page(request: Request, doc_type: str = "", client_id: str = "",
                         date_from: str = "", date_to: str = ""):
    docs = db.get_documents(
        doc_type=doc_type or None,
        client_id=int(client_id) if client_id else None,
        date_from=date_from or None,
        date_to=date_to or None,
    )
    clients = db.get_all_clients()
    return templates.TemplateResponse("documents.html", {
        "request": request,
        "documents": docs,
        "clients": clients,
        "filters": {"doc_type": doc_type, "client_id": client_id,
                     "date_from": date_from, "date_to": date_to},
        "page": "documents",
    })


@app.get("/documents/new", response_class=HTMLResponse)
async def new_document_page(request: Request, doc_type: str = "buy"):
    clients = db.get_all_clients()
    products = db.get_all_products()
    settings = db.get_all_settings()
    stock_data = db.get_stock()
    stock_map = {s["id"]: s["stock"] for s in stock_data}
    return templates.TemplateResponse("document_form.html", {
        "request": request,
        "clients": clients,
        "products": products,
        "units": UNITS,
        "settings": settings,
        "doc_type": doc_type,
        "stock_map": stock_map,
        "templates": TEMPLATES,
        "page": "new_document",
    })


@app.post("/documents/create")
async def create_document(request: Request):
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
        doc_id, doc_number = db.create_document(doc_type, client_id, doc_date, items, vat_rate, notes)
    except ValueError as e:
        return RedirectResponse(f"/documents/new?doc_type={doc_type}&error={str(e)}", status_code=303)

    # Generate PDF
    generate_invoice_pdf(doc_id, template=template)

    return RedirectResponse(f"/documents/{doc_id}?created=1", status_code=303)


@app.get("/documents/{doc_id}", response_class=HTMLResponse)
async def view_document(request: Request, doc_id: int):
    doc, items = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Dokuments nav atrasts")
    client = db.get_client(doc["client_id"])
    settings = db.get_all_settings()

    subtotal = sum(item["quantity"] * item["price_per_unit"] for item in items)
    vat_amount = subtotal * (doc["vat_rate"] / 100)
    total = subtotal + vat_amount

    return templates.TemplateResponse("document_view.html", {
        "request": request,
        "doc": doc,
        "items": items,
        "client": client,
        "settings": settings,
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "total": total,
        "templates": TEMPLATES,
        "page": "documents",
    })


@app.get("/documents/{doc_id}/pdf")
async def download_pdf(doc_id: int, template: str = "classic"):
    filepath = generate_invoice_pdf(doc_id, template=template)
    return FileResponse(filepath, media_type="application/pdf",
                        filename=os.path.basename(filepath))


@app.post("/documents/{doc_id}/delete")
async def delete_document(doc_id: int):
    db.delete_document(doc_id)
    return RedirectResponse("/documents", status_code=303)


# =============================================================================
# Stock
# =============================================================================

@app.get("/stock", response_class=HTMLResponse)
async def stock_page(request: Request, date_from: str = "", date_to: str = ""):
    stock = db.get_stock(date_from=date_from or None, date_to=date_to or None)
    return templates.TemplateResponse("stock.html", {
        "request": request,
        "stock": stock,
        "filters": {"date_from": date_from, "date_to": date_to},
        "page": "stock",
    })


# =============================================================================
# API endpoints for AJAX (quick-add from document form)
# =============================================================================

@app.post("/api/products/add")
async def api_add_product(request: Request):
    data = await request.json()
    product_id = db.add_product(data["name"], data["unit"])
    product = db.get_product(product_id)
    return JSONResponse(product)


@app.post("/api/clients/add")
async def api_add_client(request: Request):
    data = await request.json()
    client_id = db.add_client(
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
async def api_product_stock(product_id: int):
    stock = db.get_product_stock(product_id)
    return JSONResponse({"stock": stock})
