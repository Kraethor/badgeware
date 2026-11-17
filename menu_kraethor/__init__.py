# A full-resolution launcher in the blues of the dragon badge: 5 x 3 icons a
# page. Based on Pimoroni's stock menu (MIT licensed), which it sits beside
# rather than replaces. main.py on the badge chooses which launcher starts.

import json
import math
import os
import random
import sys

HERE = "/system/apps/menu_kraethor"
APPS_ROOT = "/system/apps"
DEFAULT_ICON_PATH = "/system/apps/menu/default_icon.png"

sys.path.insert(0, HERE)
sys.path.insert(0, "/")
os.chdir(HERE)

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

title_font = font.load("/system/assets/fonts/MonaSans-Medium.af")
screen.font = title_font

COLS, ROWS = 5, 3
PER_PAGE = COLS * ROWS
PITCH_X, PITCH_Y = 62, 56
GRID_X = (320 - PITCH_X * (COLS - 1)) // 2   # centre of the first column
GRID_Y = 58                                  # centre of the first row
TILE = 40

# the dragon badge palette
NIGHT = color.rgb(3, 6, 16)
PANEL = color.rgb(8, 16, 36)
TILE_IDLE = color.rgb(12, 24, 52)
TILE_ON = color.rgb(22, 52, 112)
STEEL = color.rgb(222, 230, 242)
ICE = color.rgb(120, 190, 255)
DIM = color.rgb(70, 96, 140)


def glow(alpha):
    return color.rgb(40, 120, 255, alpha)


def pulse(period, lo, hi):
    return lo + (hi - lo) * (0.5 + 0.5 * math.sin(badge.ticks / period))


# ---------------------------------------------------------------- apps

def title_case(folder):
    return " ".join(w[0].upper() + w[1:] if len(w) > 1 else w for w in folder.split("_"))


default_icon = None
try:
    default_icon = image.load(DEFAULT_ICON_PATH)
except OSError:
    pass

apps = []
for folder in sorted(os.listdir(APPS_ROOT)):
    path = "{}/{}".format(APPS_ROOT, folder)
    # the launchers themselves aren't apps
    if folder.startswith("menu") or not is_dir(path):
        continue
    if not (file_exists(path + "/__init__.py") or file_exists(path + "/__init__.mpy")):
        continue
    icon = None
    if file_exists(path + "/icon.png"):
        try:
            icon = image.load(path + "/icon.png")
        except OSError:
            pass
    apps.append({"name": title_case(folder), "path": path, "icon": icon or default_icon})

active = 0
selected_at = 0     # when the current icon was selected, for the pop-in


# ---------------------------------------------------------------- background

class Stars:
    # three layers drifting left at different speeds, twinkling a little,
    # with the odd shooting star
    LAYERS = (  # count, speed px/ms, size, colour
        (40, 0.002, 1, (60, 90, 150)),
        (22, 0.006, 1, (120, 170, 235)),
        (9, 0.014, 2, (205, 225, 255)),
    )
    stars = []
    shooter = None
    next_shooter = 4000

    @staticmethod
    def setup():
        for layer, (n, _, _, _) in enumerate(Stars.LAYERS):
            for _ in range(n):
                Stars.stars.append([random.randint(0, 319), random.randint(25, 239),
                                    layer, random.randint(0, 6283)])

    @staticmethod
    def draw():
        dt = badge.ticks_delta
        for st in Stars.stars:
            _, speed, size, rgb = Stars.LAYERS[st[2]]
            st[0] -= speed * dt
            if st[0] < -2:
                st[0] = 321
                st[1] = random.randint(25, 239)
            st[3] += dt
            a = int(255 * (0.55 + 0.45 * math.sin(st[3] / (500 + 150 * st[2]))))
            screen.pen = color.rgb(rgb[0], rgb[1], rgb[2], a)
            screen.rectangle(int(st[0]), st[1], size, size)

        # shooting star: a short streak down and to the left, fading as it goes
        now = badge.ticks
        if Stars.shooter is None and now > Stars.next_shooter:
            Stars.shooter = (random.randint(120, 330), random.randint(26, 90), now)
        if Stars.shooter:
            x0, y0, t0 = Stars.shooter
            t = (now - t0) / 700
            if t >= 1:
                Stars.shooter = None
                Stars.next_shooter = now + random.randint(6000, 14000)
            else:
                hx, hy = x0 - 160 * t, y0 + 60 * t
                for i in range(12):
                    screen.pen = color.rgb(200, 225, 255, int(230 * (1 - t) * (1 - i / 12)))
                    screen.rectangle(int(hx + i * 2.7), int(hy - i * 1.0), 2, 1)


Stars.setup()


class Terminal:
    # the stock launcher's scrolling "greeked" text, at full resolution in blue
    LINE_H = 8
    SPEED = 260         # ms per line
    lines = []          # each line is a list of word widths
    added_at = 0

    @staticmethod
    def new_line():
        words = []
        indent = random.choice((0, 0, 0, 8, 16))
        width = random.randint(60, 270)
        x = indent
        while x < width:
            w = random.randint(4, 18)
            words.append((x, w))
            x += w + 4
        return words

    @staticmethod
    def setup():
        Terminal.lines = [Terminal.new_line() for _ in range(30)]
        Terminal.added_at = badge.ticks

    @staticmethod
    def draw():
        now = badge.ticks
        while now - Terminal.added_at > Terminal.SPEED:
            Terminal.lines.pop(0)
            Terminal.lines.append(Terminal.new_line())
            Terminal.added_at += Terminal.SPEED
        shift = (now - Terminal.added_at) / Terminal.SPEED * Terminal.LINE_H
        n = len(Terminal.lines)
        for i, words in enumerate(Terminal.lines):
            y = int(240 - (n - i) * Terminal.LINE_H - shift + Terminal.LINE_H)
            if y < 26 or y > 238:
                continue
            # older lines higher up are dimmer
            fade = min(1, (y - 26) / 120)
            screen.pen = color.rgb(50, 110, 200, int(40 + 70 * fade))
            for x, w in words:
                screen.rectangle(10 + x, y, w, 2)
        # blinking cursor after the newest line
        if (now // 450) % 2:
            last = Terminal.lines[-1][-1]
            y = int(240 - Terminal.LINE_H - shift + Terminal.LINE_H) - 3
            screen.pen = color.rgb(120, 190, 255, 160)
            screen.rectangle(10 + last[0] + last[1] + 4, y, 5, 6)


Terminal.setup()

class Waterfall:
    # an SDR-style waterfall: each new row of "spectrum" appears at the top and
    # scrolls down, with carriers, bursts, drifting and wide signals in it.
    # Rows are drawn once into a ring-buffer image, so a frame is two blits.
    ROW_H = 3
    EVERY = 90          # ms per new row
    TOP = 30
    N = (240 - TOP) // ROW_H + 2
    buf = None
    head = 0            # ring index of the newest row
    signals = []
    added_at = 0

    @staticmethod
    def level_color(level):
        # navy -> blue -> ice
        level = min(max(level, 0), 1)
        if level < 0.5:
            t = level * 2
            return color.rgb(int(10 + 30 * t), int(22 + 98 * t), int(50 + 205 * t))
        t = (level - 0.5) * 2
        return color.rgb(int(40 + 140 * t), int(120 + 100 * t), 255)

    @staticmethod
    def spawn():
        kind = random.choice(("carrier", "carrier", "burst", "drift", "wide"))
        sig = {"kind": kind, "x": random.randint(10, 300), "life": random.randint(60, 260),
               "age": 0, "phase": random.randint(0, 100)}
        if kind == "wide":
            sig["w"] = random.randint(14, 30)
            sig["level"] = random.randint(25, 45) / 100
        else:
            sig["w"] = random.randint(2, 4)
            sig["level"] = random.randint(55, 95) / 100
        sig["drift"] = random.choice((-1, 1)) * random.randint(2, 6) / 10 if kind == "drift" else 0
        Waterfall.signals.append(sig)

    @staticmethod
    def new_row():
        Waterfall.head = (Waterfall.head - 1) % Waterfall.N
        img = Waterfall.buf
        y = Waterfall.head * Waterfall.ROW_H
        h = Waterfall.ROW_H
        img.pen = NIGHT
        img.rectangle(0, y, 320, h)
        for _ in range(5):      # noise floor speckle
            img.pen = Waterfall.level_color(random.randint(8, 22) / 100)
            img.rectangle(random.randint(0, 316), y, random.randint(2, 6), h)
        for sig in Waterfall.signals:
            sig["age"] += 1
            on = True
            if sig["kind"] == "burst":
                # keyed on and off, a bit like CW
                on = ((sig["age"] + sig["phase"]) // random.choice((2, 3, 6))) % 2 == 0
            if sig["kind"] == "drift":
                sig["x"] += sig["drift"] + math.sin((sig["age"] + sig["phase"]) / 9) * 0.6
            if on:
                x = int(sig["x"]) - sig["w"] // 2
                if sig["kind"] != "wide":   # a soft skirt either side
                    img.pen = Waterfall.level_color(sig["level"] * 0.35)
                    img.rectangle(x - 3, y, sig["w"] + 6, h)
                img.pen = Waterfall.level_color(sig["level"])
                img.rectangle(x, y, sig["w"], h)
        Waterfall.signals = [g for g in Waterfall.signals if g["age"] < g["life"] and -10 < g["x"] < 330]
        if len(Waterfall.signals) < 5 and random.random() < 0.08:
            Waterfall.spawn()

    @staticmethod
    def setup():
        Waterfall.buf = image(320, Waterfall.N * Waterfall.ROW_H)
        Waterfall.buf.pen = NIGHT
        Waterfall.buf.clear()
        for _ in range(3):
            Waterfall.spawn()
        for _ in range(Waterfall.N):
            Waterfall.new_row()
        Waterfall.added_at = badge.ticks

    @staticmethod
    def draw():
        now = badge.ticks
        while now - Waterfall.added_at > Waterfall.EVERY:
            Waterfall.new_row()
            Waterfall.added_at += Waterfall.EVERY
        shift = (now - Waterfall.added_at) / Waterfall.EVERY * Waterfall.ROW_H
        # buffer row j shows at TOP + ((j - head) mod N) * ROW_H + shift: two
        # blits, one either side of the wrap, clipped to the waterfall area
        y0 = int(Waterfall.TOP + shift - Waterfall.head * Waterfall.ROW_H)
        screen.clip = rect(0, Waterfall.TOP, 320, 240 - Waterfall.TOP)
        screen.blit(Waterfall.buf, vec2(0, y0))
        screen.blit(Waterfall.buf, vec2(0, y0 + Waterfall.N * Waterfall.ROW_H))
        screen.clip = rect(0, 0, 320, 240)
        # frequency scale under the header
        screen.pen = PANEL
        screen.rectangle(0, 25, 320, Waterfall.TOP - 25)
        screen.pen = DIM
        for x in range(0, 320, 16):
            screen.rectangle(x, 25, 1, 4 if x % 64 == 0 else 2)


class Circuit:
    # PCB traces drawn once into an image, with pulses of light running along them
    GRID = 8
    board = None
    paths = []          # each a list of (x, y) vertices
    lengths = []        # each a list of segment lengths, in steps
    pulses = []
    flashes = []        # (x, y, start ticks)

    TRACE = color.rgb(22, 48, 98)
    PAD = color.rgb(40, 86, 160)

    @staticmethod
    def make_path():
        g = Circuit.GRID
        x = random.randint(1, 39) * g
        y = random.randint(4, 29) * g
        dirs = ((1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1))
        d = random.choice(dirs)
        pts = [(x, y)]
        for _ in range(random.randint(2, 5)):
            n = random.randint(2, 7)
            nx, ny = x + d[0] * n * g, y + d[1] * n * g
            if not (4 <= nx <= 316 and 30 <= ny <= 236):
                break
            x, y = nx, ny
            pts.append((x, y))
            # turn 45 or 90 degrees, never straight back
            options = [o for o in dirs if o != d and o != (-d[0], -d[1])
                       and abs(o[0] - d[0]) + abs(o[1] - d[1]) <= 2]
            d = random.choice(options)
        return pts if len(pts) > 1 else None

    @staticmethod
    def setup():
        img = image(320, 240)
        img.pen = NIGHT
        img.clear()
        while len(Circuit.paths) < 18:
            pts = Circuit.make_path()
            if pts is None:
                continue
            Circuit.paths.append(pts)
            Circuit.lengths.append([max(abs(b[0] - a[0]), abs(b[1] - a[1])) for a, b in zip(pts, pts[1:])])
            img.pen = Circuit.TRACE
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                steps = max(abs(x1 - x0), abs(y1 - y0))
                sx, sy = (x1 > x0) - (x1 < x0), (y1 > y0) - (y1 < y0)
                if sx and sy:
                    for k in range(steps + 1):
                        img.rectangle(x0 + sx * k, y0 + sy * k, 2, 2)
                else:
                    img.rectangle(min(x0, x1), min(y0, y1), abs(x1 - x0) + 2, abs(y1 - y0) + 2)
            for px, py in (pts[0], pts[-1]):
                img.pen = Circuit.PAD
                img.shape(shape.circle(px + 1, py + 1, 3.5))
                img.pen = NIGHT
                img.shape(shape.circle(px + 1, py + 1, 1.5))
        Circuit.board = img

    @staticmethod
    def point(path, lens, s):
        for (x0, y0), (x1, y1), n in zip(path, path[1:], lens):
            if s <= n:
                t = s / n if n else 0
                return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            s -= n
        return path[-1]

    @staticmethod
    def draw():
        screen.blit(Circuit.board, vec2(0, 0))
        dt = badge.ticks_delta
        now = badge.ticks

        if len(Circuit.pulses) < 4 and random.random() < 0.04:
            i = random.randint(0, len(Circuit.paths) - 1)
            Circuit.pulses.append([i, 0.0, random.randint(5, 9) / 100, random.random() < 0.5])

        keep = []
        for p in Circuit.pulses:
            i, s, speed, backwards = p
            path, lens = Circuit.paths[i], Circuit.lengths[i]
            total = sum(lens)
            p[1] = s = s + speed * dt
            if s >= total:
                end = path[0] if backwards else path[-1]
                Circuit.flashes.append((end[0] + 1, end[1] + 1, now))
                continue
            keep.append(p)
            for k in range(6):      # head and fading tail
                d = s - k * 3
                if d < 0:
                    break
                x, y = Circuit.point(path, lens, total - d if backwards else d)
                screen.pen = color.rgb(150, 205, 255, 230 - k * 38)
                screen.rectangle(int(x), int(y), 2 if k else 3, 2 if k else 3)
        Circuit.pulses = keep

        live = []
        for x, y, t0 in Circuit.flashes:
            t = (now - t0) / 600
            if t < 1:
                live.append((x, y, t0))
                screen.pen = color.rgb(120, 190, 255, int(200 * (1 - t)))
                screen.shape(shape.circle(x, y, 3.5 + 4 * t))
        Circuit.flashes = live


class HexDump:
    # scrolling hex dump; each line is drawn once into a small image and reused
    LINE_H = 9
    SPEED = 300         # ms per line
    COUNT = (240 - 26) // 9 + 2
    WORDS = (b"KRAETHOR", b"BadgeOS", b"RP2350", b"CYW43439", b"TCRC", b"SKYWARN",
             b"hello, world", b"/system/apps", b"secrets.py", b"0xDEADBEEF", b"dragon")
    images = []
    order = []          # indexes into images, oldest first
    offset = 0x1F400
    added_at = 0

    @staticmethod
    def row_bytes():
        r = random.random()
        if r < 0.15:
            return bytes(16)
        if r < 0.22:
            return b"\xff" * 16
        data = bytearray(os.urandom(16))
        if r < 0.5:
            word = random.choice(HexDump.WORDS)[:16]
            at = random.randint(0, 16 - len(word))
            data[at:at + len(word)] = word
        return bytes(data)

    @staticmethod
    def render(img):
        data = HexDump.row_bytes()
        img.pen = NIGHT
        img.clear()
        img.pen = color.rgb(50, 80, 130)
        img.text("{:06X}".format(HexDump.offset), 0, 0)
        img.pen = color.rgb(70, 130, 220)
        for i, b in enumerate(data):
            img.text("{:02X}".format(b), 42 + i * 14 + (4 if i >= 8 else 0), 0)
        img.pen = color.rgb(110, 170, 240)
        for i, b in enumerate(data):
            img.text(chr(b) if 32 <= b < 127 else ".", 274 + i * 3, 0)
        HexDump.offset = (HexDump.offset + 16) & 0xFFFFFF

    @staticmethod
    def setup():
        for _ in range(HexDump.COUNT):
            img = image(320, HexDump.LINE_H)
            img.font = font.sins
            HexDump.render(img)
            HexDump.images.append(img)
        HexDump.order = list(range(HexDump.COUNT))
        HexDump.added_at = badge.ticks

    @staticmethod
    def draw():
        now = badge.ticks
        while now - HexDump.added_at > HexDump.SPEED:
            oldest = HexDump.order.pop(0)
            HexDump.render(HexDump.images[oldest])
            HexDump.order.append(oldest)
            HexDump.added_at += HexDump.SPEED
        shift = (now - HexDump.added_at) / HexDump.SPEED * HexDump.LINE_H
        n = len(HexDump.order)
        for k, idx in enumerate(HexDump.order):
            y = int(240 - (n - k) * HexDump.LINE_H - shift + HexDump.LINE_H)
            if y < 26 - HexDump.LINE_H or y > 239:
                continue
            img = HexDump.images[idx]
            img.alpha = int(90 + 120 * min(1, max(0, (y - 26) / 140)))
            screen.blit(img, vec2(6, y))


# set up lazily, the first time each background is shown
BACKGROUNDS = (
    ("Starfield", Stars.draw, None),
    ("Terminal", Terminal.draw, None),
    ("Hex dump", HexDump.draw, HexDump.setup),
    ("Waterfall", Waterfall.draw, Waterfall.setup),
    ("Circuit", Circuit.draw, Circuit.setup),
)
_ready = set()
STATE_FILE = "/state/menu_kraethor.json"


def load_background():
    try:
        with open(STATE_FILE) as f:
            return int(json.loads(f.read()).get("background", 0)) % len(BACKGROUNDS)
    except (OSError, ValueError, AttributeError):
        return 0


def save_background(index):
    try:
        try:
            os.stat("/state")
        except OSError:
            os.mkdir("/state")
        with open(STATE_FILE, "w") as f:
            f.write(json.dumps({"background": index}))
    except OSError:
        pass    # not worth failing the launcher over


background = load_background()
background_note_until = 0


def draw_background():
    screen.pen = NIGHT
    screen.clear()
    name, draw, setup = BACKGROUNDS[background]
    if setup and name not in _ready:
        setup()
        _ready.add(name)
    draw()
    # a soft band of light behind the grid
    for i in range(6):
        screen.pen = color.rgb(20, 50, 120, 10)
        screen.shape(shape.rounded_rectangle(8 + i * 3, 32 + i * 3, 304 - i * 6, 168 - i * 6, 14))


def draw_header():
    screen.pen = PANEL
    screen.rectangle(0, 0, 320, 24)
    screen.pen = glow(int(pulse(700, 60, 140)))
    screen.rectangle(0, 24, 320, 1)

    screen.pen = ICE
    screen.text("KRAETHOR", 8, 4, font_size=14)

    # battery
    level = (badge.ticks / 20) % 100 if badge.is_charging() else badge.battery_level()
    x, y, w, h = 288, 7, 22, 11
    screen.pen = ICE
    screen.shape(shape.rounded_rectangle(x, y, w, h, 2).stroke(1.5))
    screen.rectangle(x + w, y + 3, 2, h - 6)
    screen.pen = ICE if level > 20 else color.rgb(255, 110, 90)
    screen.rectangle(x + 2, y + 2, int((w - 4) * level / 100), h - 4)


# ---------------------------------------------------------------- grid

def tile_centre(slot):
    return GRID_X + (slot % COLS) * PITCH_X, GRID_Y + (slot // COLS) * PITCH_Y


def draw_grid():
    page = active // PER_PAGE
    for slot in range(PER_PAGE):
        i = page * PER_PAGE + slot
        if i >= len(apps):
            break
        app = apps[i]
        cx, cy = tile_centre(slot)
        on = i == active
        size = TILE
        if on:
            # a quick pop when an icon is selected
            t = min((badge.ticks - selected_at) / 160, 1)
            size = TILE + 6 * math.sin(t * math.pi) + 2
        half = size / 2

        if on:
            for r, a in ((10, 30), (6, 60), (3, 110)):
                screen.pen = glow(int(a * pulse(500, 0.6, 1.0)))
                screen.shape(shape.rounded_rectangle(cx - half - r, cy - half - r,
                                                     size + 2 * r, size + 2 * r, 10 + r))

        screen.pen = color.rgb(0, 0, 0, 90)
        screen.shape(shape.rounded_rectangle(cx - half + 1, cy - half + 2, size, size, 10))
        screen.pen = TILE_ON if on else TILE_IDLE
        screen.shape(shape.rounded_rectangle(cx - half, cy - half, size, size, 10))
        screen.pen = ICE if on else color.rgb(60, 90, 150, 160)
        screen.shape(shape.rounded_rectangle(cx - half, cy - half, size, size, 10).stroke(1.5 if on else 1))

        icon = app["icon"]
        if icon:
            icon.alpha = 255 if on else 150
            screen.blit(icon, vec2(cx - icon.width // 2, cy - icon.height // 2))


def draw_label():
    label = apps[active]["name"]
    if badge.ticks < background_note_until:
        label = "Background: " + BACKGROUNDS[background][0]
    w, _ = screen.measure_text(label, font_size=14)
    x = (320 - w) / 2
    screen.pen = PANEL
    screen.shape(shape.rounded_rectangle(x - 10, 200, w + 20, 22, 8))
    screen.pen = glow(int(pulse(500, 120, 220)))
    screen.shape(shape.rounded_rectangle(x - 10, 200, w + 20, 22, 8).stroke(1.5))
    screen.pen = STEEL
    screen.text(label, x, 203, font_size=14)


def draw_pages():
    pages = (len(apps) + PER_PAGE - 1) // PER_PAGE
    if pages < 2:
        return
    page = active // PER_PAGE
    x = 320 - 8 - pages * 10
    for p in range(pages):
        screen.pen = ICE if p == page else DIM
        screen.shape(shape.circle(x + p * 10 + 4, 211, 3 if p == page else 2))


# ---------------------------------------------------------------- loop

def hand_over():
    # Leave the display the way the stock launcher does. The mode and font carry
    # over into the app, and several stock apps (clock, badge, sense...) never set
    # their own: they expect the boot default low-res mode and the "sins" font.
    badge.mode(LORES | VSYNC)
    screen.font = font.sins
    screen.pen = getattr(badge, "default_pen", None) or color.white


fade = 0


def update():
    global active, selected_at, fade, background, background_note_until

    if not apps:
        screen.pen = NIGHT
        screen.clear()
        screen.pen = STEEL
        screen.text("No apps found in /system/apps", 40, 110, font_size=14)
        return None

    before = active
    if badge.pressed(BUTTON_C):
        active = min(active + 1, len(apps) - 1)
    if badge.pressed(BUTTON_A):
        active = max(active - 1, 0)
    if badge.pressed(BUTTON_DOWN):
        active = min(active + COLS, len(apps) - 1)
    if badge.pressed(BUTTON_UP):
        if active >= COLS:
            active -= COLS
        else:
            # UP from the top row cycles the background
            background = (background + 1) % len(BACKGROUNDS)
            background_note_until = badge.ticks + 1500
            save_background(background)
    if active != before:
        selected_at = badge.ticks

    if badge.pressed(BUTTON_B):
        hand_over()
        return apps[active]["path"]

    draw_background()
    draw_header()
    draw_grid()
    draw_label()
    draw_pages()

    # fade in from black on start, like the stock launcher
    if fade < 255:
        screen.pen = color.rgb(0, 0, 0, 255 - fade)
        screen.rectangle(0, 0, 320, 240)
        fade = min(fade + 30, 255)
    return None


# "on_exit" is called if callable, else returned verbatim by launch()
on_exit = run(update).result
