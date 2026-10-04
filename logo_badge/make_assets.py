"""Builds the two background images for the Logo Badge app (run on a computer,
not on the badge).

    python make_assets.py my-logo.png    use your own picture or logo
    python make_assets.py                redraw the built-in placeholder

Writes, next to this script:
    assets/bg.png      320x240 front page, with room for the name plate
    assets/bg_dim.png  darkened and softened copy, shown behind the other pages

Needs: pip install pillow
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

OUT = Path(__file__).parent / "assets"
W, H = 320, 240
ART_H = 186          # the name plate covers everything below this
BACKDROP = (14, 18, 30)


def placeholder():
    # a stand-in emblem, drawn large and scaled down for smooth edges
    k = 4
    im = Image.new("RGB", (W * k, H * k), BACKDROP)
    d = ImageDraw.Draw(im)
    cx, cy = W * k // 2, 96 * k

    # soft glow behind the emblem
    glow = Image.new("RGB", im.size, BACKDROP)
    ImageDraw.Draw(glow).ellipse((cx - 110 * k, cy - 110 * k, cx + 110 * k, cy + 110 * k), fill=(20, 52, 110))
    im = Image.blend(im, glow.filter(ImageFilter.GaussianBlur(28 * k)), 0.85)
    d = ImageDraw.Draw(im)

    def hexagon(r):
        return [(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))
                for a in range(-90, 270, 60)]

    d.polygon(hexagon(84 * k), fill=(40, 120, 255))
    d.polygon(hexagon(79 * k), fill=(222, 230, 242))
    d.polygon(hexagon(74 * k), fill=(16, 26, 50))

    # the usual "picture goes here" mark: a sun over two hills
    d.ellipse((cx + 14 * k, cy - 44 * k, cx + 38 * k, cy - 20 * k), fill=(120, 190, 255))
    d.polygon([(cx - 52 * k, cy + 26 * k), (cx - 18 * k, cy - 26 * k), (cx + 16 * k, cy + 26 * k)], fill=(40, 120, 255))
    d.polygon([(cx - 12 * k, cy + 26 * k), (cx + 20 * k, cy - 8 * k), (cx + 52 * k, cy + 26 * k)], fill=(120, 190, 255))

    caption = "YOUR LOGO"
    font = ImageFont.load_default(size=11 * k)
    w = d.textlength(caption, font=font)
    d.text((cx - w / 2, cy + 34 * k), caption, font=font, fill=(222, 230, 242))

    return im.resize((W, H), Image.LANCZOS)


def from_picture(path):
    art = Image.open(path)
    if art.mode in ("RGBA", "LA", "P"):
        # flatten transparency onto the backdrop
        art = art.convert("RGBA")
        flat = Image.new("RGBA", art.size, BACKDROP + (255,))
        art = Image.alpha_composite(flat, art)
    art = art.convert("RGB")

    # continue the picture's own edge colour behind it, so it doesn't sit in a box
    corners = [art.getpixel(p) for p in ((0, 0), (art.width - 1, 0), (0, art.height - 1), (art.width - 1, art.height - 1))]
    fill = tuple(sum(c[i] for c in corners) // 4 for i in range(3))

    # fit the whole picture above the name plate
    scale = min(W / art.width, (ART_H + 20) / art.height)
    art = art.resize((max(1, round(art.width * scale)), max(1, round(art.height * scale))), Image.LANCZOS)
    im = Image.new("RGB", (W, H), fill)
    im.paste(art, ((W - art.width) // 2, max(0, (ART_H + 20 - art.height) // 2)))
    return im


bg = from_picture(sys.argv[1]) if len(sys.argv) > 1 else placeholder()

dim = bg.filter(ImageFilter.GaussianBlur(1.6))
dim = ImageEnhance.Brightness(dim).enhance(0.38)
dim = Image.blend(dim, Image.new("RGB", (W, H), (6, 14, 34)), 0.25)

OUT.mkdir(exist_ok=True)
bg.save(OUT / "bg.png", optimize=True)
dim.save(OUT / "bg_dim.png", optimize=True)
for name in ("bg.png", "bg_dim.png"):
    print("wrote", OUT / name, (OUT / name).stat().st_size, "bytes")
