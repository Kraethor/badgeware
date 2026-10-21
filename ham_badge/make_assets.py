"""Builds the background and launcher icon for the Ham Badge app (run on a
computer, not on the badge).

    python make_assets.py my-logo.png    use your own logo
    python make_assets.py                use the built-in default logo

The front page puts the logo in a panel on the left, the name on the right and
the callsign across the bottom (the name and callsign are drawn on the badge, so
they are not baked into the image here).

Writes, next to this script:
    assets/bg.png      320x240 front page: black, logo in the left panel
    icon.png           24x24 launcher icon, the logo on black

Needs: pip install pillow
"""
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
OUT = HERE / "assets"

# the logo used when none is given on the command line
DEFAULT_LOGO = r"C:\Users\tron\OneDrive - Nortron\Pictures\Logos\tcrc-B.jpg"

W, H = 320, 240
BACKDROP = (0, 0, 0)     # black, as asked
DIVIDER_X = 172          # left panel holds the logo, right side holds the name
STRIP_TOP = 184          # the callsign strip runs along the bottom, below this
PAD = 10                 # breathing room around the logo in its panel


def flatten(path):
    art = Image.open(path)
    if art.mode in ("RGBA", "LA", "P"):
        art = art.convert("RGBA")
        flat = Image.new("RGBA", art.size, BACKDROP + (255,))
        art = Image.alpha_composite(flat, art)
    return art.convert("RGB")


def front(art):
    # fit the whole logo into the left panel, above the callsign strip
    box_w = DIVIDER_X - 2 * PAD
    box_h = STRIP_TOP - 2 * PAD
    scale = min(box_w / art.width, box_h / art.height)
    logo = art.resize((max(1, round(art.width * scale)), max(1, round(art.height * scale))), Image.LANCZOS)

    im = Image.new("RGB", (W, H), BACKDROP)
    x = (DIVIDER_X - logo.width) // 2
    y = (STRIP_TOP - logo.height) // 2
    im.paste(logo, (x, y))
    return im


def icon(art):
    # the logo on black, shrunk to the launcher's 24x24
    im = Image.new("RGB", (24, 24), BACKDROP)
    scale = min(24 / art.width, 24 / art.height)
    logo = art.resize((max(1, round(art.width * scale)), max(1, round(art.height * scale))), Image.LANCZOS)
    im.paste(logo, ((24 - logo.width) // 2, (24 - logo.height) // 2))
    return im.convert("RGBA")


art = flatten(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_LOGO)

OUT.mkdir(exist_ok=True)
front(art).save(OUT / "bg.png", optimize=True)
icon(art).save(HERE / "icon.png", optimize=True)
for p in (OUT / "bg.png", HERE / "icon.png"):
    print("wrote", p, p.stat().st_size, "bytes")
