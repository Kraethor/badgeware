import json
import math
import secrets

import requests
import wifi

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

ui_font = font.load("/system/assets/fonts/MonaSans-Medium.af")
screen.font = ui_font

# Where "overhead" is. Add LATITUDE and LONGITUDE to secrets.py to fix the
# position; without them the badge looks up roughly where its WiFi connection is.
HOME_LAT = getattr(secrets, "LATITUDE", None)
HOME_LON = getattr(secrets, "LONGITUDE", None)

LOCATE_URL = "http://ip-api.com/json/?fields=status,lat,lon,city"
PLANES_URL = "https://api.adsb.lol/v2/point/{:.4f}/{:.4f}/{}"
# adsb.lol asks every client to identify itself with some contact detail
HEADERS = {"User-Agent": "tufty-planes-overhead/1.0 (+https://github.com/Kraethor)"}

RANGES = [10, 25, 50, 100]  # nautical miles, switched with UP / DOWN
REFRESH = 20                # seconds between fetches
SWEEP_PERIOD = 4000         # milliseconds per turn of the radar sweep
MAX_BLIPS = 40              # most aircraft drawn at once
MAX_LABELS = 8              # most callsigns shown when labels are on

# the scope and the readout panel beside it
SX, SY, SR = 116, 124, 106
PANEL_X = 232

BACKDROP = color.rgb(0, 10, 5)
GRID = color.rgb(0, 150, 60, 90)
PHOSPHOR = color.rgb(60, 255, 120)
DIM = color.rgb(40, 170, 90)
AMBER = color.rgb(255, 190, 60)
ALERT = color.rgb(255, 90, 70)

COMPASS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

home_name = "fixed position" if HOME_LAT is not None else None
range_index = 1
planes = []           # everything from the last fetch, nearest first
selected_hex = None   # the aircraft shown in the panel, followed across fetches
fetched_at = None
fetch_due = True
fetch_failed = False
fetched_range = None
locate_shown = False
locate_retry_at = 0
show_labels = False

# shapes that never change are built once
rings = [shape.circle(SX, SY, SR * i / 4).stroke(1) for i in range(1, 5)]
crosshair = [shape.line(SX - SR, SY, SX + SR, SY, 1), shape.line(SX, SY - SR, SX, SY + SR, 1)]
blip = shape.custom([vec2(0, -6), vec2(4.5, 5), vec2(0, 2.5), vec2(-4.5, 5)])
blip_dot = shape.circle(0, 0, 2.5)
select_ring = shape.circle(0, 0, 10).stroke(1.5)


def locate():
    # one-off lookup of roughly where the badge is, from its internet address
    global HOME_LAT, HOME_LON, home_name
    try:
        r = requests.get(LOCATE_URL)
        j = r.json()
        r.close()
        if j.get("status") == "success":
            HOME_LAT, HOME_LON = float(j["lat"]), float(j["lon"])
            home_name = j.get("city") or "here"
            return True
    except (OSError, ValueError, KeyError):
        pass
    return False


def fetch_planes():
    global planes, fetched_at, fetch_failed, fetched_range, selected_hex

    fetched_range = RANGES[range_index]
    try:
        r = requests.get(PLANES_URL.format(HOME_LAT, HOME_LON, fetched_range), headers=HEADERS)
        if r.status_code != 200:
            r.close()
            raise ValueError
        aircraft = r.json().get("ac", [])
        r.close()
    except (OSError, ValueError):
        fetch_failed = True
        fetched_at = badge.ticks
        return

    found = []
    for a in aircraft:
        alt = a.get("alt_baro")
        dst, bearing = a.get("dst"), a.get("dir")
        if alt == "ground" or dst is None or bearing is None:
            continue
        b = math.radians(bearing)
        label = (a.get("flight") or "").strip() or a.get("r") or a.get("hex", "?")
        found.append({
            "hex": a.get("hex"),
            "label": label,
            "type": a.get("t") or "",
            "reg": a.get("r") or "",
            "alt": alt,
            "climb": a.get("baro_rate") or 0,
            "gs": a.get("gs"),
            "track": a.get("track"),
            # position as nautical miles east and north of home
            "e": dst * math.sin(b),
            "n": dst * math.cos(b),
        })

    found.sort(key=lambda p: p["e"] * p["e"] + p["n"] * p["n"])
    planes = found
    fetched_at = badge.ticks
    fetch_failed = False

    if selected_hex not in [p["hex"] for p in planes]:
        selected_hex = None


def position(p):
    # where the aircraft should be by now, flying on from its last report
    e, n = p["e"], p["n"]
    if p["gs"] and p["track"] is not None and fetched_at is not None:
        hours = (badge.ticks - fetched_at) / 3600000
        t = math.radians(p["track"])
        e += p["gs"] * hours * math.sin(t)
        n += p["gs"] * hours * math.cos(t)
    return e, n


def in_range():
    limit = RANGES[range_index]
    visible = []
    for p in planes:
        e, n = position(p)
        d = math.sqrt(e * e + n * n)
        if d <= limit:
            visible.append((d, e, n, p))
    visible.sort(key=lambda v: v[0])
    count = len(visible)
    if count > MAX_BLIPS:
        # too busy to draw everything: thin it evenly from nearest to farthest
        visible = [visible[int(i * count / MAX_BLIPS)] for i in range(MAX_BLIPS)]
    return visible, count


def text_right(text, x, y, size):
    w, _ = screen.measure_text(text, font_size=size)
    screen.text(text, x - w, y, font_size=size)


def draw_scope(visible, selected):
    limit = RANGES[range_index]
    sweep = (badge.ticks % SWEEP_PERIOD) / SWEEP_PERIOD * 360

    screen.pen = GRID
    for ring in rings:
        screen.shape(ring)
    for line in crosshair:
        screen.shape(line)

    # the sweep, brightest at its leading edge
    for i in range(6):
        screen.pen = color.rgb(60, 255, 120, 46 - i * 7)
        screen.shape(shape.pie(SX, SY, SR, sweep - (i + 1) * 9, sweep - i * 9))

    screen.pen = DIM
    screen.text("N", SX - 4, SY - SR - 13, font_size=11)
    for i in (2, 4):
        screen.text(str(limit * i // 4), SX + 3, SY - (SR * i / 4) + 2, font_size=9)

    for i, (d, e, n, p) in enumerate(visible):
        x = SX + (e / limit) * SR
        y = SY - (n / limit) * SR
        is_selected = selected is not None and p["hex"] == selected["hex"]

        # each blip is repainted as the sweep passes, then fades until it returns
        bearing = math.degrees(math.atan2(e, n)) % 360
        age = ((sweep - bearing) % 360) / 360
        glow = int(255 - 170 * age)

        if is_selected:
            screen.pen = AMBER
        else:
            screen.pen = color.rgb(60, 255, 120, glow)

        if p["track"] is not None:
            blip.transform = mat3().translate(x, y).rotate(p["track"])
            screen.shape(blip)
        else:
            blip_dot.transform = mat3().translate(x, y)
            screen.shape(blip_dot)

        if is_selected:
            select_ring.transform = mat3().translate(x, y)
            screen.shape(select_ring)

        if is_selected or (show_labels and i < MAX_LABELS):
            screen.text(p["label"], x + 9, y - 5, font_size=10)

    # home
    screen.pen = PHOSPHOR
    screen.shape(shape.circle(SX, SY, 2))


def draw_panel(count, selected):
    x = PANEL_X
    right = screen.width - 6

    screen.pen = PHOSPHOR
    screen.text("PLANES", x, 4, font_size=15)
    screen.pen = DIM
    screen.text("{} within {} nm".format(count, RANGES[range_index]), x, 21, font_size=10)

    screen.pen = GRID
    screen.shape(shape.line(x, 36, right, 36, 1))

    if selected is None:
        screen.pen = DIM
        screen.text("Clear skies", x, 44, font_size=12)
    else:
        d, e, n, p = selected["d"], selected["e"], selected["n"], selected

        screen.pen = AMBER
        size = 20
        while size > 11 and screen.measure_text(p["label"], font_size=size)[0] > right - x:
            size -= 1
        screen.text(p["label"], x, 40, font_size=size)

        screen.pen = DIM
        screen.text("{} {}".format(p["type"], p["reg"]).strip() or "unknown type", x, 63, font_size=10)

        bearing = math.degrees(math.atan2(e, n)) % 360
        if p["climb"] > 300:
            trend = " up"
        elif p["climb"] < -300:
            trend = " dn"
        else:
            trend = ""
        rows = (
            ("ALT", "{} ft{}".format(p["alt"], trend) if p["alt"] is not None else "-"),
            ("SPD", "{} kt".format(round(p["gs"])) if p["gs"] else "-"),
            ("DST", "{:.1f} nm".format(d)),
            ("BRG", "{:03d} {}".format(round(bearing) % 360, COMPASS[round(bearing / 45) % 8])),
            ("HDG", "{:03d}".format(round(p["track"]) % 360) if p["track"] is not None else "-"),
        )
        y = 82
        for name, value in rows:
            screen.pen = DIM
            screen.text(name, x, y + 2, font_size=9)
            screen.pen = PHOSPHOR
            text_right(value, right, y, 12)
            y += 19

    # footer: data age and the button hints
    screen.pen = GRID
    screen.shape(shape.line(x, 184, right, 184, 1))
    if fetch_failed:
        screen.pen = ALERT
        screen.text("No data, retrying", x, 189, font_size=10)
    elif fetched_at is not None:
        screen.pen = DIM
        screen.text("Updated {}s ago".format((badge.ticks - fetched_at) // 1000), x, 189, font_size=10)
    screen.pen = DIM
    screen.text("A/C  select", x, 205, font_size=9)
    screen.text("UP/DN  range", x, 215, font_size=9)
    screen.text("B  labels", x, 225, font_size=9)


def draw_message(text):
    screen.pen = PHOSPHOR
    w, _ = screen.measure_text(text, font_size=14)
    screen.text(text, (screen.width - w) / 2, 112, font_size=14)


def update():
    global range_index, selected_hex, show_labels, fetch_due, locate_shown, locate_retry_at

    screen.pen = BACKDROP
    screen.clear()

    if not wifi.connect():
        draw_message("Connecting to {}...".format(secrets.WIFI_SSID))
        return

    if HOME_LAT is None:
        draw_message("Finding where we are...")
        # the lookup blocks, so it runs on the frame after the message is shown
        if locate_shown and badge.ticks >= locate_retry_at:
            if not locate():
                locate_retry_at = badge.ticks + 5000
        locate_shown = True
        return

    if badge.pressed(BUTTON_UP):
        range_index = max(0, range_index - 1)
    if badge.pressed(BUTTON_DOWN):
        range_index = min(len(RANGES) - 1, range_index + 1)

    # the fetch blocks too, so it runs on the frame after "updating" is shown
    if fetch_due:
        fetch_planes()
        fetch_due = False
    elif (fetched_at is None or (badge.ticks - fetched_at) / 1000 > REFRESH
          or RANGES[range_index] > fetched_range):
        fetch_due = True
    if badge.pressed(BUTTON_B):
        show_labels = not show_labels

    visible, count = in_range()

    # step the selection through the aircraft on the scope, nearest first
    if visible and (badge.pressed(BUTTON_A) or badge.pressed(BUTTON_C)):
        order = [v[3]["hex"] for v in visible]
        i = order.index(selected_hex) if selected_hex in order else 0
        if badge.pressed(BUTTON_C):
            i = (i + 1) % len(order)
        else:
            i = (i - 1) % len(order)
        selected_hex = order[i]

    selected = None
    for d, e, n, p in visible:
        if p["hex"] == selected_hex:
            selected = dict(p)
            selected.update({"d": d, "e": e, "n": n})
            break
    if selected is None and visible:
        d, e, n, p = visible[0]
        selected = dict(p)
        selected.update({"d": d, "e": e, "n": n})

    draw_scope(visible, selected)
    draw_panel(count, selected)

    if fetch_due:
        screen.pen = AMBER
        screen.text("updating", 6, 4, font_size=10)
    elif home_name:
        screen.pen = DIM
        screen.text(home_name, 6, 4, font_size=10)


def on_exit():
    pass


run(update)
