import json
import math
import secrets

import requests
import wifi

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

ui_font = font.load("/system/assets/fonts/MonaSans-Medium.af")
screen.font = ui_font

# USGS summary feeds, switched with B
FEED_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/{}.geojson"
FEEDS = (
    ("M2.5+  past day", "2.5_day"),
    ("M4.5+  past week", "4.5_week"),
    ("Significant  past month", "significant_month"),
)
HEADERS = {"User-Agent": "tufty-earthquakes/1.0"}
REFRESH = 300   # seconds between fetches
RETRY = 15      # seconds before trying again after a failed fetch
ZOOMS = (1, 2.5, 6)

# the map sits between a title bar and the readout for the selected quake
MAP_Y, MAP_H = 22, 160
MAP_CY = MAP_H / 2
INFO_Y = MAP_Y + MAP_H
BASE_SCALE = screen.width / 360   # pixels per degree with the whole world in view

OCEAN = color.rgb(8, 16, 30)
LAND = color.rgb(46, 66, 86)
BAR = color.rgb(4, 8, 16)
TEXT = color.rgb(226, 232, 240)
MUTED = color.rgb(130, 150, 172)
ALERT = color.rgb(255, 90, 70)

feed_index = 0
quakes = []        # newest first
selected = 0
zoom_index = 0
generated = 0      # when USGS built the feed, ms since 1970 (UTC)
fetched_at = None
fetch_due = True
fetch_failed = False
map_view = None    # the view and fetch the cached map was drawn for

map_image = image(screen.width, MAP_H)
map_image.antialias = image.X2
coastlines = []


def load_coastlines():
    # the same world outline the ISS tracker uses
    with open("/system/assets/world.geo.json", "r") as f:
        for country in json.loads(f.read()):
            for polygon in country["polygons"]:
                lons = [p[0] for p in polygon]
                coastlines.append((min(lons), max(lons),
                                   shape.custom([vec2(p[0], -p[1]) for p in polygon])))


def fetch_quakes():
    global quakes, generated, fetched_at, fetch_failed, selected

    fetched_at = badge.ticks
    try:
        r = requests.get(FEED_URL.format(FEEDS[feed_index][1]), headers=HEADERS)
        if r.status_code != 200:
            r.close()
            raise ValueError
        j = r.json()
        r.close()
    except (OSError, ValueError):
        fetch_failed = True
        return

    found = []
    for feature in j.get("features", []):
        props = feature.get("properties", {})
        coords = feature.get("geometry", {}).get("coordinates")
        if props.get("mag") is None or not coords:
            continue
        found.append({
            "mag": props["mag"],
            "place": props.get("place") or "Unknown location",
            "time": props.get("time") or 0,
            "lon": coords[0],
            "lat": coords[1],
            "depth": coords[2] if len(coords) > 2 else None,
        })

    found.sort(key=lambda q: -q["time"])
    quakes = found
    generated = j.get("metadata", {}).get("generated", 0)
    fetch_failed = False
    selected = 0


def mag_color(mag, alpha=255):
    # yellow for small, through orange, to red for major
    t = min(max((mag - 2.5) / 4.0, 0), 1)
    return color.rgb(255, int(225 - 185 * t), int(70 - 40 * t), alpha)


def mag_radius(mag):
    return 2.5 + max(mag - 2.0, 0) * 2.0


def age_text(q):
    # the feed's own timestamp stands in for a clock, so the badge's time
    # zone setting doesn't matter
    seconds = (generated - q["time"]) // 1000 + (badge.ticks - fetched_at) // 1000
    minutes = max(seconds // 60, 0)
    if minutes < 60:
        return "{} min ago".format(minutes)
    if minutes < 48 * 60:
        return "{}h {:02d}m ago".format(minutes // 60, minutes % 60)
    return "{} days ago".format(minutes // 1440)


def view():
    # centre and scale of the map: the whole world, or zoomed on the selection
    zoom = ZOOMS[zoom_index]
    if zoom == 1 or not quakes:
        return 0, 0, 1
    q = quakes[selected]
    # keep the top and bottom of the world from scrolling into view
    limit = 90 - (90 / zoom)
    return q["lon"], min(max(q["lat"], -limit), limit), zoom


def to_screen(lon, lat, v):
    clon, clat, zoom = v
    k = BASE_SCALE * zoom
    dlon = (lon - clon + 180) % 360 - 180   # shortest way round the globe
    return screen.width / 2 + dlon * k, MAP_Y + MAP_CY - (lat - clat) * k


def draw_map(v):
    # the coastline and the quakes are slow to draw, so they are drawn once
    # per view and per fetch, then reused every frame
    global map_view

    if (v, fetched_at) != map_view:
        clon, clat, zoom = v
        k = BASE_SCALE * zoom
        half = screen.width / 2 / k
        map_image.pen = OCEAN
        map_image.clear()
        map_image.pen = LAND
        for o in (-360, 0, 360):
            m = mat3().translate(screen.width / 2 - (clon - o) * k, MAP_CY + clat * k).scale(k, k)
            for lo, hi, coast in coastlines:
                if hi + o >= clon - half and lo + o <= clon + half:
                    coast.transform = m
                    map_image.shape(coast)

        # oldest first so the newest are drawn on top
        for i in range(len(quakes) - 1, -1, -1):
            q = quakes[i]
            x, y = to_screen(q["lon"], q["lat"], v)
            y -= MAP_Y
            r = mag_radius(q["mag"])
            map_image.pen = mag_color(q["mag"], 110)
            map_image.shape(shape.circle(x, y, r))
            map_image.pen = mag_color(q["mag"], 230)
            map_image.shape(shape.circle(x, y, r).stroke(1))
        map_view = (v, fetched_at)

    screen.blit(map_image, vec2(0, MAP_Y))


def draw_selected(v):
    screen.clip = rect(0, MAP_Y, screen.width, MAP_H)

    if quakes:
        q = quakes[selected]
        x, y = to_screen(q["lon"], q["lat"], v)
        r = mag_radius(q["mag"])

        # ripples spreading from the selected quake
        for phase in (0, 0.5):
            t = ((badge.ticks / 1600) + phase) % 1
            screen.pen = mag_color(q["mag"], int(200 * (1 - t)))
            screen.shape(shape.circle(x, y, r + t * 22).stroke(1.5))

        screen.pen = mag_color(q["mag"])
        screen.shape(shape.circle(x, y, r))
        screen.pen = color.rgb(255, 255, 255)
        screen.shape(shape.circle(x, y, r + 1.5).stroke(1.5))

    screen.clip = rect(0, 0, screen.width, screen.height)


def fit_text(text, x, y, size, max_width):
    while size > 9 and screen.measure_text(text, font_size=size)[0] > max_width:
        size -= 1
    screen.text(text, x, y, font_size=size)


def draw_bars():
    screen.pen = BAR
    screen.rectangle(0, 0, screen.width, MAP_Y)
    screen.rectangle(0, INFO_Y, screen.width, screen.height - INFO_Y)

    screen.pen = TEXT
    screen.text("EARTHQUAKES", 6, 4, font_size=13)
    label = FEEDS[feed_index][0]
    screen.pen = MUTED
    if fetch_due:
        label = "updating..."
    elif fetch_failed:
        label = "no data, retrying"
        screen.pen = ALERT
    w, _ = screen.measure_text(label, font_size=10)
    screen.text(label, screen.width - 6 - w, 6, font_size=10)

    if not quakes:
        screen.pen = MUTED
        screen.text("Nothing reported in this feed" if fetched_at is not None and not fetch_failed
                    else "Waiting for data", 8, INFO_Y + 20, font_size=12)
        return

    q = quakes[selected]

    # magnitude on the left, details beside it
    screen.pen = mag_color(q["mag"])
    mag = "{:.1f}".format(q["mag"])
    screen.text("M", 8, INFO_Y + 8, font_size=11)
    screen.text(mag, 8, INFO_Y + 18, font_size=30)
    mw, _ = screen.measure_text(mag, font_size=30)
    x = max(8 + mw + 12, 74)

    screen.pen = TEXT
    fit_text(q["place"], x, INFO_Y + 7, 14, screen.width - x - 6)

    screen.pen = MUTED
    detail = age_text(q)
    if q["depth"] is not None:
        detail += "   depth {} km".format(round(q["depth"]))
    screen.text(detail, x, INFO_Y + 26, font_size=11)
    screen.text("{} of {}    A/C step   UP/DN zoom   B feed".format(selected + 1, len(quakes)),
                x, INFO_Y + 42, font_size=9)


def update():
    global selected, zoom_index, feed_index, fetch_due, fetched_at

    if not wifi.connect():
        screen.pen = OCEAN
        screen.clear()
        screen.pen = TEXT
        text = "Connecting to {}...".format(secrets.WIFI_SSID)
        w, _ = screen.measure_text(text, font_size=14)
        screen.text(text, (screen.width - w) / 2, 112, font_size=14)
        return

    if badge.pressed(BUTTON_B):
        feed_index = (feed_index + 1) % len(FEEDS)
        fetch_due = True
    elif fetch_due:
        # the fetch blocks, so it runs on the frame after "updating" is shown
        fetch_quakes()
        fetch_due = False
    elif fetched_at is None or (badge.ticks - fetched_at) / 1000 > (RETRY if fetch_failed else REFRESH):
        fetch_due = True

    if quakes:
        if badge.pressed(BUTTON_C):
            selected = (selected + 1) % len(quakes)
        if badge.pressed(BUTTON_A):
            selected = (selected - 1) % len(quakes)
    if badge.pressed(BUTTON_UP):
        zoom_index = min(zoom_index + 1, len(ZOOMS) - 1)
    if badge.pressed(BUTTON_DOWN):
        zoom_index = max(zoom_index - 1, 0)

    v = view()
    draw_map(v)
    draw_selected(v)
    draw_bars()


def on_exit():
    pass


load_coastlines()

run(update)
