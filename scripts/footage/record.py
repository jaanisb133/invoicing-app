"""Record the landing-page footage: the real invoice editor, in real time.

Makes app/static/media/editor.mp4 (desktop) or editor-phone.mp4 (--phone) plus a
poster frame. The landing page claims the clip is not sped up, so keep it that way.

    VREKINI_DB_PATH=/tmp/footage.db python scripts/footage/seed.py
    VREKINI_DB_PATH=/tmp/footage.db uvicorn app.main:app --port 8766 &
    python scripts/footage/record.py [--phone] [--base http://localhost:8766] [--chromium /path/to/chrome]

Needs Playwright (Python) and ffmpeg with libx264. Frames come from Chrome's own
screencast, so Playwright's bundled ffmpeg is not needed.
"""
import argparse
import base64
import os
import subprocess
import tempfile

from playwright.sync_api import sync_playwright

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
MEDIA = os.path.join(ROOT, "app", "static", "media")

ap = argparse.ArgumentParser()
ap.add_argument("--phone", action="store_true")
ap.add_argument("--base", default="http://localhost:8766")
ap.add_argument("--chromium", default=None, help="Chrome/Chromium executable, if Playwright's own is not installed")
args = ap.parse_args()

phone = args.phone
viewport = {"width": 390, "height": 844} if phone else {"width": 1440, "height": 900}
name = "editor-phone" if phone else "editor"

with sync_playwright() as p:
    launch = {"args": ["--no-sandbox"]}
    if args.chromium:
        launch["executable_path"] = args.chromium
    browser = p.chromium.launch(**launch)

    ctx = browser.new_context(viewport=viewport)
    page = ctx.new_page()
    page.goto(args.base + "/login")
    page.fill("input[name=username]", "paraugs")
    page.fill("input[name=password]", "paraugs12345")
    page.click("button[type=submit]")
    page.wait_for_load_state("networkidle")
    state = ctx.storage_state()
    ctx.close()

    ctx = browser.new_context(viewport=viewport, color_scheme="light", storage_state=state,
                              device_scale_factor=2 if phone else 1, is_mobile=phone, has_touch=phone)
    page = ctx.new_page()
    page.goto(args.base + "/documents/new?doc_type=sell")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(900)

    frames = []
    cdp = ctx.new_cdp_session(page)

    def on_frame(ev):
        frames.append((ev["metadata"]["timestamp"], ev["data"]))
        cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})

    cdp.on("Page.screencastFrame", on_frame)
    cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92,
                                      "maxWidth": viewport["width"] * (2 if phone else 1),
                                      "maxHeight": viewport["height"] * (2 if phone else 1)})
    page.wait_for_timeout(400)

    # Human pace, keyboard only: client, two lines with remembered prices, save.
    k = page.keyboard
    page.locator("#clientSearchInput").click()
    page.wait_for_timeout(500); k.type("bērzu", delay=110); page.wait_for_timeout(450); k.press("Enter")
    page.wait_for_timeout(700)
    page.locator("#product-name-0").scroll_into_view_if_needed()
    page.locator("#product-name-0").click()
    page.wait_for_timeout(300); k.type("fasād", delay=110); page.wait_for_timeout(400); k.press("Enter")
    page.wait_for_timeout(500); k.press("Control+A"); k.type("120", delay=140); page.wait_for_timeout(300)
    k.press("Enter"); page.wait_for_timeout(250); k.press("Enter"); page.wait_for_timeout(250); k.press("Enter")
    page.wait_for_timeout(500); k.type("sastat", delay=110); page.wait_for_timeout(400); k.press("Enter")
    page.wait_for_timeout(500); k.press("Control+A"); k.type("6", delay=140); page.wait_for_timeout(1800)
    total = page.locator("#railTotal").inner_text()
    k.press("Control+Enter")
    page.wait_for_url("**/documents/*?created=1*")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(2600)
    cdp.send("Page.stopScreencast")
    ctx.close()
    browser.close()

print("total on screen:", total, "| frames:", len(frames))
work = tempfile.mkdtemp()
lines = []
end = frames[-1][0] + 1.0
for i, (ts, data) in enumerate(frames):
    fn = os.path.join(work, f"{i:05d}.jpg")
    with open(fn, "wb") as f:
        f.write(base64.b64decode(data))
    nxt = frames[i + 1][0] if i + 1 < len(frames) else end
    lines += [f"file '{fn}'", f"duration {max(nxt - ts, 0.001):.4f}"]
lines.append(f"file '{os.path.join(work, f'{len(frames) - 1:05d}.jpg')}'")
listing = os.path.join(work, "list.txt")
with open(listing, "w") as f:
    f.write("\n".join(lines))

scale = "scale=780:-2" if phone else "scale=1280:800"
video = os.path.join(MEDIA, name + ".mp4")
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", listing,
                "-vf", f"fps=30,{scale}:flags=lanczos,format=yuv420p", "-c:v", "libx264", "-preset", "slow",
                "-crf", "25" if phone else "24", "-movflags", "+faststart", "-an", video], check=True)
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "9" if phone else "8.4", "-i", video,
                "-frames:v", "1", "-q:v", "5" if phone else "4", os.path.join(MEDIA, name + "-poster.jpg")], check=True)
print("wrote", video)
