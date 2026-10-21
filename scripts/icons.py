"""Render every icon from the brand mark (the receipt with a V in _site_bar.html).

    python scripts/icons.py            # needs Playwright + Pillow; not app dependencies

Writes to app/static/icons/: the PWA icons and apple-touch icon on the ground tile, and the
favicons: an SVG that turns light on dark browser tabs, PNGs at 16/32/48/96 (Google wants
a multiple of 48) and favicon.ico (16/32/48, also served at /favicon.ico). 16 px gets its own
drawing on the pixel grid, with two teeth instead of four: the full mark is mush at that size.
After changing the icons, bump ICON_VERSION in _icons.html so browsers drop the cached ones."""
import io
import os
from PIL import Image
from playwright.sync_api import sync_playwright

OUT = os.path.join(os.path.dirname(__file__), "..", "app", "static", "icons") + os.sep
CHROMIUM = os.getenv("CHROME_PATH", "/opt/pw-browsers/chromium")
INK, GROUND = "#141414", "#f2f4f7"
RECEIPT = "M6 3.5h16a1 1 0 0 1 1 1V24l-2.5-1.8L18 24l-2.5-1.8L13 24l-2.5-1.8L8 24l-2.5-1.8L5 22.6V4.5a1 1 0 0 1 1-1z"
V = "M10 9.5l4 7.5 4-7.5"
RECEIPT16 = "M3 1h10a1 1 0 0 1 1 1v13l-3-2-3 2-3-2-3 2V2a1 1 0 0 1 1-1z"
V16 = "M5 4.75l3 5.75 3-5.75"
SQUARE = "3.25 3 21.5 21.5"      # the mark centred in a square box, filling it


def svg(receipt=RECEIPT, v=V, box=SQUARE, sw=2.2, cut="#fff", adaptive=False):
    if adaptive:
        style = (f"<style>.r{{fill:{INK}}}.v{{stroke:{cut}}}"
                 f"@media (prefers-color-scheme:dark){{.r{{fill:{GROUND}}}.v{{stroke:{INK}}}}}</style>")
        r, c = 'class="r"', 'class="v"'
    else:
        style, r, c = "", f'fill="{INK}"', f'stroke="{cut}"'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{box}">{style}<path {r} d="{receipt}"/>'
            f'<path {c} d="{v}" fill="none" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def tile(size, mark_share, radius_share):
    """The mark on the ground colour, for home screens."""
    mark = svg(box="4 2.5 20 22.5", cut=GROUND)
    w = size * mark_share
    return (f'<div style="width:{size}px;height:{size}px;background:{GROUND};border-radius:{size * radius_share}px;'
            f'display:grid;place-items:center">{mark.replace("<svg ", f"<svg width={w} height={w * 22.5 / 20} ", 1)}</div>')


def bare(size):
    mark = svg(RECEIPT16, V16, "0 0 16 16", 2) if size == 16 else svg()
    return mark.replace("<svg ", f"<svg width={size} height={size} style=display:block ", 1)


TILES = [
    ("icon-192.png", 192, .56, .22),
    ("icon-512.png", 512, .56, .22),
    ("icon-maskable-192.png", 192, .44, 0),   # maskable: full bleed, mark inside the 80% safe circle
    ("icon-maskable-512.png", 512, .44, 0),
    ("apple-touch-icon.png", 180, .54, 0),    # iOS rounds the corners itself
]

with open(OUT + "favicon.svg", "w") as f:
    f.write(svg(adaptive=True) + "\n")

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM, args=["--no-sandbox"])

    def shoot(html, size):
        pg = browser.new_page(viewport={"width": size, "height": size}, device_scale_factor=1)
        pg.set_content(f'<html><body style="margin:0;background:transparent">{html}</body></html>')
        png = pg.screenshot(omit_background=True, clip={"x": 0, "y": 0, "width": size, "height": size})
        pg.close()
        return Image.open(io.BytesIO(png)).convert("RGBA")

    for name, size, share, radius in TILES:
        shoot(tile(size, share, radius), size).save(OUT + name, optimize=True)
        print(name)
    small = {}
    for size in (16, 32, 48, 96):
        small[size] = shoot(bare(size), size)
        small[size].save(OUT + f"favicon-{size}.png", optimize=True)
        print(f"favicon-{size}.png")
    browser.close()

small[48].save(OUT + "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)], append_images=[small[16], small[32]])
print("favicon.ico favicon.svg")
