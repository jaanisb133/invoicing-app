"""Portfolio screenshots of the real app, on the showcase account (showcase.py).

    VREKINI_DB_PATH=/tmp/showcase.db python scripts/footage/showcase.py
    VREKINI_DB_PATH=/tmp/showcase.db uvicorn app.main:app --port 8766 &
    python scripts/footage/screens.py --out DIR [--base http://localhost:8766] [--chromium PATH] [--vendor DIR]

Desktop at 1440x900 and phones at 390x844, both at 2x, in the dark and light themes;
the landing page; and the three PDF templates of one invoice, rendered from the real
PDFs (needs pdftoppm). Writes PNG; convert for the web where the images are used.
--vendor serves Chart.js and flatpickr from a folder where cdn.jsdelivr.net is blocked.
"""
import argparse
import os
import subprocess
import sys
import tempfile

from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--base", default="http://localhost:8766")
ap.add_argument("--chromium", default=None)
ap.add_argument("--vendor", default=None)
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)
DESK = {"width": 1440, "height": 900}
PHONE = {"width": 390, "height": 844}


def vendor(ctx):
    if not args.vendor:
        return

    def serve(route):
        url = route.request.url
        f = "chart.umd.min.js" if "chart" in url else "flatpickr.min.css" if url.endswith(".css") else "flatpickr.min.js"
        route.fulfill(path=os.path.join(args.vendor, f))
    ctx.route("https://cdn.jsdelivr.net/**", serve)


def settle(page, ms=700):
    page.wait_for_load_state("networkidle")
    page.evaluate("document.activeElement && document.activeElement.blur()")
    page.wait_for_timeout(ms)


def fill_editor(page):
    """Client and two lines, typed the way a person would; nothing is saved."""
    k = page.keyboard
    page.locator("#clientSearchInput").click()
    k.type("bērzu", delay=30); page.wait_for_timeout(400); k.press("Enter"); page.wait_for_timeout(500)
    page.locator("#product-name-0").click()
    k.type("produkt", delay=30); page.wait_for_timeout(400); k.press("Enter")
    page.wait_for_timeout(300); k.press("Control+A"); k.type("120"); k.press("Enter")
    page.wait_for_timeout(200); k.press("Enter"); page.wait_for_timeout(200); k.press("Enter")
    page.wait_for_timeout(300); k.type("attēl", delay=30); page.wait_for_timeout(400); k.press("Enter")
    page.wait_for_timeout(300); k.press("Control+A"); k.type("6")
    page.wait_for_timeout(900)


with sync_playwright() as p:
    launch = {"args": ["--no-sandbox"]}
    if args.chromium:
        launch["executable_path"] = args.chromium
    browser = p.chromium.launch(**launch)

    ctx = browser.new_context(viewport=DESK)
    vendor(ctx)
    page = ctx.new_page()
    page.goto(args.base + "/login")
    page.fill("input[name=username]", "paraugs")
    page.fill("input[name=password]", "paraugs12345")
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    state = ctx.storage_state()
    ctx.close()

    for theme in ("dark", "light"):
        for kind, vp in (("desktop", DESK), ("phone", PHONE)):
            phone = kind == "phone"
            ctx = browser.new_context(viewport=vp, device_scale_factor=2, is_mobile=phone, has_touch=phone,
                                      storage_state=state, color_scheme=theme)
            ctx.add_init_script(f"try {{ localStorage.setItem('vrekini-theme', '{theme}');"
                                f" localStorage.setItem('dashChartGrain', 'month') }} catch (e) {{}}")
            vendor(ctx)
            page = ctx.new_page()
            shots = [("dashboard", "/"), ("documents", "/documents")]
            for name, path in shots:
                page.goto(args.base + path)
                if name == "dashboard":     # this year by month: the studio's growth at a glance
                    page.click("#btnThisYear")
                settle(page, 1200 if name == "dashboard" else 600)
                page.screenshot(path=os.path.join(args.out, f"{name}-{kind}-{theme}.png"))
            # the newest invoice, as its page shows it
            href = page.locator("a[href^='/documents/']").filter(has_text="26-").first.get_attribute("href")
            page.goto(args.base + href.split("?")[0])
            settle(page)
            page.screenshot(path=os.path.join(args.out, f"invoice-{kind}-{theme}.png"))
            page.goto(args.base + "/documents/new?doc_type=sell")
            settle(page)
            fill_editor(page)
            if phone:     # the lines and the running total
                page.evaluate("""() => { const h = [...document.querySelectorAll('h2, h3, .card-title')]
                    .find(e => e.textContent.trim() === 'Rindas'); if (h) window.scrollTo(0, h.getBoundingClientRect().top + scrollY - 76); }""")
            page.evaluate("document.activeElement && document.activeElement.blur()")
            page.wait_for_timeout(500)
            page.screenshot(path=os.path.join(args.out, f"editor-{kind}-{theme}.png"))
            ctx.close()

    # The public landing page, as a visitor sees it (light only)
    for kind, vp in (("desktop", DESK), ("phone", PHONE)):
        ctx = browser.new_context(viewport=vp, device_scale_factor=2, is_mobile=kind == "phone", has_touch=kind == "phone")
        vendor(ctx)
        page = ctx.new_page()
        page.goto(args.base + "/")
        settle(page, 1200)
        page.screenshot(path=os.path.join(args.out, f"landing-{kind}.png"))
        ctx.close()
    browser.close()

# The three PDF templates of today's invoice, from the real generator
sys.path.insert(0, ROOT)
from app import database as db, pdf_generator as pg  # noqa: E402
uid = db.get_user_by_username("paraugs")["id"]
conn = db.get_connection()
doc_id = conn.execute("SELECT id FROM documents WHERE user_id = ? AND doc_type = 'sell' ORDER BY doc_date DESC, id DESC LIMIT 1",
                      (uid,)).fetchone()[0]
conn.close()
work = tempfile.mkdtemp()
for template in ("classic", "modern", "minimal"):
    pdf = pg.generate_invoice_pdf(doc_id, template=template)
    subprocess.run(["pdftoppm", "-png", "-singlefile", "-r", "200", pdf, os.path.join(args.out, f"pdf-{template}")], check=True)
    os.remove(pdf)
print("wrote", args.out)
