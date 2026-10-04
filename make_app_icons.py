"""Draws the 24x24 launcher icons for the apps in this repo
as pixel art in the style of the stock icons. Needs: pip install pillow
"""
from pathlib import Path
from PIL import Image

HERE = Path(__file__).parent


def build(rows, palette, out):
    assert len(rows) == 22 and all(len(r) == 22 for r in rows), [len(r) for r in rows]
    icon = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            icon.putpixel((x + 1, y + 1), palette[ch])
    # 1px white border around the silhouette, like the stock icons
    solid = [[icon.getpixel((x, y))[3] > 0 for x in range(24)] for y in range(24)]
    for y in range(24):
        for x in range(24):
            if not solid[y][x] and any(
                    0 <= x + dx < 24 and 0 <= y + dy < 24 and solid[y + dy][x + dx]
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                icon.putpixel((x, y), (255, 255, 255, 255))
    icon.save(out)
    print("wrote", out)


RADAR = {
    ".": (0, 0, 0, 0),
    "k": (16, 28, 24, 255),      # bezel
    "d": (6, 40, 22, 255),       # screen
    "g": (20, 110, 55, 255),     # grid
    "s": (40, 170, 85, 255),     # sweep
    "b": (110, 255, 150, 255),   # sweep edge / blips
    "a": (255, 190, 60, 255),    # selected blip
}
build([
    "......kkkkkkkkkk......",
    "....kkddddgsssbdkk....",
    "...kdddddgdsssbdddk...",
    "..kdddgggggssbbddddk..",
    ".kdddgdddgdssbdgddddk.",
    ".kddgddddgssbbddgdddk.",
    "kdddgdbddgssbdddgddddk",
    "kddgddddgggsbdgddgdddk",
    "kddgdddgddgbbddgdgdddk",
    "kddgdddgddsbdddgdgdddk",
    "kgggggggggbgggggggggdk",
    "kddgdddgddgdddagdgdddk",
    "kddgdddgddgdddgddgdddk",
    "kddgddddgggggdgddgdddk",
    "kdddgddddgddddddgddddk",
    ".kddgdbddgddddddgdddk.",
    ".kdddgdddgdddddgddddk.",
    "..kdddgggggggggddddk..",
    "...kdddddgdddddbddk...",
    "....kkdddgdddddkkk....",
    "......kkkkkkkkkk......",
    "......................",
], RADAR, HERE / "planes_overhead" / "icon.png")

QUAKE = {
    ".": (0, 0, 0, 0),
    "k": (30, 24, 28, 255),      # outline
    "p": (244, 238, 222, 255),   # paper
    "l": (200, 205, 215, 255),   # grid line
    "r": (220, 50, 50, 255),     # trace
}
build([
    "kkkkkkkkkkkkkkkkkkkkkk",
    "kppppppppppppppppppppk",
    "kpppppppprpppppppppppk",
    "kpppppppprpppppppppppk",
    "kllllllllrlllllllllllk",
    "kpppppppprpppppppppppk",
    "kppppppprrpprppppppppk",
    "kppppppprrpprppppppppk",
    "kllllrllrrlrrllllllllk",
    "kppprrprrprrrprppppppk",
    "krrrrprrrprprrrrrrrrrk",
    "kpppppprrprprprppppppk",
    "kllllllrrlrlrllllllllk",
    "kppppppprprprppppppppk",
    "kppppppprprrpppppppppk",
    "kppppppprprrpppppppppk",
    "kllllllllrrllllllllllk",
    "kppppppppprppppppppppk",
    "kppppppppprppppppppppk",
    "kppppppppppppppppppppk",
    "kppppppppppppppppppppk",
    "kkkkkkkkkkkkkkkkkkkkkk",
], QUAKE, HERE / "earthquakes" / "icon.png")

LOGO = {
    ".": (0, 0, 0, 0),
    "k": (16, 22, 40, 255),      # outline
    "n": (28, 40, 72, 255),      # card
    "b": (47, 125, 240, 255),    # emblem
    "c": (130, 200, 255, 255),   # emblem highlight
    "s": (222, 230, 242, 255),   # name plate text
    "g": (120, 140, 170, 255),   # role text
    "h": (90, 100, 120, 255),    # lanyard clip
}
build([
    ".........khhk.........",
    ".........khhk.........",
    "..kkkkkkkkhhkkkkkkkk..",
    ".knnnnnnnkkkknnnnnnnk.",
    ".knnnnnnnnnnnnnnnnnnk.",
    ".knnnnnnnnbbnnnnnnnnk.",
    ".knnnnnnbbbbbbnnnnnnk.",
    ".knnnnnbbbbbbbbnnnnnk.",
    ".knnnnnbbbccbbbnnnnnk.",
    ".knnnnnbbccccbbnnnnnk.",
    ".knnnnnbbccccbbnnnnnk.",
    ".knnnnnbbbccbbbnnnnnk.",
    ".knnnnnbbbbbbbbnnnnnk.",
    ".knnnnnnbbbbbbnnnnnnk.",
    ".knnnnnnnnbbnnnnnnnnk.",
    ".knnnnnnnnnnnnnnnnnnk.",
    ".knnnssssssssssssnnnk.",
    ".knnnnnnnnnnnnnnnnnnk.",
    ".knnnnnggggggggnnnnnk.",
    ".knnnnnnnnnnnnnnnnnnk.",
    "..kkkkkkkkkkkkkkkkkk..",
    "......................",
], LOGO, HERE / "logo_badge" / "icon.png")
