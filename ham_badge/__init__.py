import sys
import os

sys.path.insert(0, "/system/apps/ham_badge")
os.chdir("/system/apps/ham_badge")

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

CX = screen.width / 2

# the badge details
callsign = "KD0MLN"       # the 0 gets a slash drawn through it, ham style
name_lines = ["Tron", "Howard"]

# the front art: black with the TCRC logo in the left panel (make_assets.py)
front_bg = image.load("assets/bg.png")

ui_font = font.load("/system/assets/fonts/MonaSans-Medium.af")
screen.font = ui_font

WHITE = color.rgb(255, 255, 255)
SHADOW = color.rgb(0, 0, 0, 200)

# layout: logo in the left panel, name on the right, callsign across the bottom
DIVIDER_X = 172
STRIP_TOP = 184


def shadow_text(text, x, y, size, pen):
    screen.pen = SHADOW
    screen.text(text, x + 1, y + 2, font_size=size)
    screen.pen = pen
    screen.text(text, x, y, font_size=size)


def center_text_at(cx, text, y, size, pen):
    w, _ = screen.measure_text(text, font_size=size)
    shadow_text(text, cx - (w / 2), y, size, pen)


def fit_size(text, size, max_width):
    # shrink long text until it fits the space available
    while size > 10:
        w, _ = screen.measure_text(text, font_size=size)
        if w <= max_width:
            break
        size -= 1
    return size


def draw_front():
    screen.blit(front_bg, vec2(0, 0))

    # faint dividers: between logo and name, and above the callsign
    screen.pen = color.rgb(255, 255, 255, 55)
    screen.shape(shape.line(DIVIDER_X, 16, DIVIDER_X, STRIP_TOP - 16, 2))
    screen.shape(shape.line(0, STRIP_TOP, screen.width, STRIP_TOP, 2))

    # name on the right, stacked and centred in its panel
    name_cx = DIVIDER_X + (screen.width - DIVIDER_X) / 2
    region_w = screen.width - DIVIDER_X - 20
    size = fit_size(max(name_lines, key=len), 32, region_w)
    line_h = size + 4
    top = (STRIP_TOP - line_h * len(name_lines)) / 2
    for i, line in enumerate(name_lines):
        center_text_at(name_cx, line, top + i * line_h, size, WHITE)

    # callsign across the whole bottom, with a slash drawn through its zero
    size = fit_size(callsign, 48, screen.width - 16)
    w, h = screen.measure_text(callsign, font_size=size)
    x = CX - w / 2
    y = STRIP_TOP + (screen.height - STRIP_TOP - h) / 2
    shadow_text(callsign, x, y, size, WHITE)

    zi = callsign.find("0")
    if zi >= 0:
        left = x + (screen.measure_text(callsign[:zi], font_size=size)[0] if zi else 0)
        right = x + screen.measure_text(callsign[:zi + 1], font_size=size)[0]
        w0 = right - left
        cx0 = (left + right) / 2
        hx = w0 * 0.40                # horizontal reach, near the oval's sides
        # font_size is the em and MonaSans caps sit low in it; measured against a
        # badge photo, the digit's centre is ~0.67 of size below the text top
        cy = y + size * 0.67
        hy = size * 0.31              # just inside the cap height, no overshoot
        weight = max(3, size * 0.07)
        # lower-left to upper-right, through the centre, with a drop shadow
        screen.pen = SHADOW
        screen.shape(shape.line(cx0 - hx + 1, cy + hy + 2, cx0 + hx + 1, cy - hy + 2, weight))
        screen.pen = WHITE
        screen.shape(shape.line(cx0 - hx, cy + hy, cx0 + hx, cy - hy, weight))


def init():
    pass


def update():
    draw_front()


def on_exit():
    pass


run(update)
