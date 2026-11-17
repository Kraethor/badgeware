import os

import bluetooth

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

ui_font = font.load("/system/assets/fonts/MonaSans-Medium.af")
screen.font = ui_font

GONE_AFTER = 30000  # ms without hearing a device before it is shown as gone
NEW_FOR = 6000      # ms a device stays marked as new
RESORT_EVERY = 1000 # ms between re-sorts, so the list doesn't jitter
MAX_SEEN = 300      # devices remembered; the longest unheard are dropped first
MAX_PENDING = 400   # adverts queued between frames; extras are dropped

TOP_H = 22
ROW_H = 18
LIST_Y = TOP_H + 2
FOOT_Y = 222
ROWS = (FOOT_Y - LIST_Y) // ROW_H

BG = color.rgb(8, 12, 20)
BAR = color.rgb(4, 6, 12)
ROW_SEL = color.rgb(30, 44, 66)
TEXT = color.rgb(226, 232, 240)
MUTED = color.rgb(130, 150, 172)
DIM = color.rgb(70, 82, 98)
NEW = color.rgb(150, 160, 255)
WARM = color.rgb(255, 200, 70)
ALERT = color.rgb(255, 90, 70)

SORTS = ("newest", "latest", "signal", "name")

_IRQ_SCAN_RESULT = 5
_IRQ_SCAN_DONE = 6

# Used when assets/companies.bin is missing (see make_companies.py).
# Names from the Bluetooth SIG company identifier list.
FALLBACK_COMPANIES = {
    0x0002: "Intel", 0x0006: "Microsoft", 0x000F: "Broadcom", 0x0059: "Nordic Semiconductor",
    0x004C: "Apple", 0x0075: "Samsung Electronics", 0x0087: "Garmin International",
    0x00E0: "Google", 0x0131: "Cypress Semiconductor", 0x0157: "Anhui Huami",
    0x0171: "Amazon.com Services", 0x01DA: "Logitech", 0x02E5: "Espressif Systems",
    0x038F: "Xiaomi", 0x0499: "Ruuvi Innovations", 0x0822: "adafruit industries",
}

# 16-bit service UUIDs: the standard services by name, member UUIDs by their owner
SERVICES = {
    0x180A: "Device Info", 0x180D: "Heart Rate", 0x180F: "Battery", 0x1812: "HID",
    0x1816: "Cycling Speed", 0x1818: "Cycling Power", 0x181A: "Env Sensing",
    0x1826: "Fitness Machine",
    0xFCF1: "Google", 0xFD44: "Apple", 0xFD5A: "Samsung", 0xFD6F: "Apple",
    0xFE03: "Amazon", 0xFE07: "Sonos", 0xFE2C: "Google", 0xFE9F: "Google",
    0xFEAA: "Google", 0xFEED: "Tile",
}
MEMBER_OWNERS = ("Google", "Apple", "Samsung", "Amazon", "Sonos", "Tile")

# First byte of Apple's manufacturer data. Apple doesn't publish these; they
# come from public reverse engineering of the Continuity protocol.
APPLE_KINDS = {
    0x02: "iBeacon", 0x05: "AirDrop", 0x07: "AirPods", 0x09: "AirPlay",
    0x0C: "Handoff", 0x0F: "Nearby Action", 0x10: "Nearby Info", 0x12: "Find My",
}

seen = {}           # address bytes -> record dict
order = []          # addresses in the current sort order
pending = []        # raw adverts from the radio, processed once per frame
sort_index = 0
selected = 0
top = 0
paused = False
detail = False
last_sort = 0
ble_error = None

_company_cache = {}
try:
    _company_count = os.stat("assets/companies.bin")[6] // 32
except OSError:
    _company_count = 0


def company(cid):
    # binary search of the fixed-size records in companies.bin
    if cid in _company_cache:
        return _company_cache[cid]
    name = None
    if _company_count:
        try:
            with open("assets/companies.bin", "rb") as f:
                lo, hi = 0, _company_count - 1
                while lo <= hi:
                    mid = (lo + hi) // 2
                    f.seek(mid * 32)
                    rec = f.read(32)
                    rid = rec[0] | (rec[1] << 8)
                    if rid == cid:
                        name = rec[2:].rstrip(b"\0").decode()
                        break
                    if rid < cid:
                        lo = mid + 1
                    else:
                        hi = mid - 1
        except (OSError, UnicodeError):
            pass
    if name is None:
        name = FALLBACK_COMPANIES.get(cid) or "ID 0x{:04X}".format(cid)
    _company_cache[cid] = name
    return name


def on_irq(event, data):
    # keep this short: copy the advert out (the buffers are reused) and queue it
    if event == _IRQ_SCAN_RESULT:
        if len(pending) < MAX_PENDING:
            addr_type, addr, adv_type, rssi, adv = data
            pending.append((addr_type, bytes(addr), adv_type, rssi, bytes(adv)))


def start_scan():
    global ble_error
    try:
        # scan until told to stop, listening all the time, asking for scan responses
        ble.gap_scan(0, 30000, 30000, True)
        ble_error = None
    except OSError as e:
        ble_error = "Bluetooth scan failed ({})".format(e)


def stop_scan():
    try:
        ble.gap_scan(None)
    except OSError:
        pass


def text_of(raw):
    try:
        text = raw.decode()
    except UnicodeError:
        text = "".join(chr(b) if 32 <= b < 127 else "?" for b in raw)
    text = text.strip("\0 ")
    return text or None


def parse(adv):
    # walk the advertising data structures: length, type, value
    out = {}
    i = 0
    while i + 1 < len(adv):
        length = adv[i]
        if length == 0:
            break
        kind = adv[i + 1]
        value = adv[i + 2:i + 1 + length]
        if kind in (0x08, 0x09):            # short / complete local name
            name = text_of(value)
            if name:
                out["name"] = name
        elif kind == 0xFF and len(value) >= 2:   # manufacturer specific data
            out["mfr"] = value[0] | (value[1] << 8)
            out["mdata"] = value[2:]
        elif kind == 0x0A and len(value) == 1:   # TX power level
            out["tx"] = value[0] - 256 if value[0] > 127 else value[0]
        elif kind in (0x02, 0x03):               # 16-bit service UUID lists
            out.setdefault("uuids", []).extend(
                value[j] | (value[j + 1] << 8) for j in range(0, len(value) - 1, 2))
        elif kind == 0x16 and len(value) >= 2:   # service data, 16-bit UUID
            out.setdefault("uuids", []).append(value[0] | (value[1] << 8))
        i += 1 + length
    return out


def absorb():
    # move queued adverts into the device list
    n = len(pending)
    if not n:
        return
    batch = pending[:n]
    del pending[:n]
    now = badge.ticks

    for addr_type, addr, adv_type, rssi, adv in batch:
        dev = seen.get(addr)
        if dev is None:
            dev = {
                "addr": addr, "random": addr_type == 1, "first": now,
                "rssi": rssi, "best": rssi, "name": None, "mfr": None,
                "kind": None, "tx": None, "uuids": [], "connectable": False,
            }
            seen[addr] = dev
        else:
            # smooth the reading; single adverts jump around a lot
            dev["rssi"] = (dev["rssi"] * 3 + rssi) // 4
            dev["best"] = max(dev["best"], rssi)
        dev["last"] = now
        if adv_type in (0, 1):      # ADV_IND, ADV_DIRECT_IND
            dev["connectable"] = True

        info = parse(adv)
        if "name" in info:
            dev["name"] = info["name"]
        if "mfr" in info:
            dev["mfr"] = info["mfr"]
            mdata = info["mdata"]
            if info["mfr"] == 0x004C and mdata:
                dev["kind"] = APPLE_KINDS.get(mdata[0], dev["kind"])
        if "tx" in info:
            dev["tx"] = info["tx"]
        for u in info.get("uuids", ()):
            if u not in dev["uuids"] and len(dev["uuids"]) < 8:
                dev["uuids"].append(u)

    if len(seen) > MAX_SEEN:
        oldest = sorted(seen.values(), key=lambda d: d["last"])
        for dev in oldest[:len(seen) - MAX_SEEN]:
            del seen[dev["addr"]]


def gone(dev):
    return badge.ticks - dev["last"] > GONE_AFTER


def maker(dev):
    if dev["mfr"] is not None:
        return company(dev["mfr"])
    for u in dev["uuids"]:
        if SERVICES.get(u) in MEMBER_OWNERS:
            return SERVICES[u]
    return None


def addr_text(addr):
    return ":".join("{:02X}".format(b) for b in addr)


def title(dev):
    return dev["name"] or dev["kind"] or addr_text(dev["addr"])


def resort():
    global order, selected, last_sort

    last_sort = badge.ticks
    keep = order[selected] if order and selected < len(order) else None
    devs = list(seen.values())
    mode = SORTS[sort_index]
    if mode == "newest":
        devs.sort(key=lambda d: -d["first"])
    elif mode == "latest":
        # devices in range by signal, then the gone ones, most recently heard first
        devs.sort(key=lambda d: (1, -d["last"]) if gone(d) else (0, -d["rssi"]))
    elif mode == "signal":
        devs.sort(key=lambda d: -d["rssi"])
    else:
        # named devices alphabetically, then the rest by signal
        devs.sort(key=lambda d: (0, d["name"].lower(), 0) if d["name"] else (1, "", -d["rssi"]))
    order = [d["addr"] for d in devs]
    if mode != "newest" and keep in seen:
        selected = order.index(keep)
    selected = min(selected, max(len(order) - 1, 0))


def rssi_color(rssi):
    # red when weak, through yellow, to green when strong
    t = min(max((rssi + 95) / 45, 0), 1)
    if t < 0.5:
        return color.rgb(255, int(90 + 330 * t), 70)
    return color.rgb(int(255 - 330 * (t - 0.5)), 255, int(70 + 60 * (t - 0.5)))


def draw_bars(x, y, rssi, faded):
    level = 0 if rssi < -90 else 1 if rssi < -80 else 2 if rssi < -70 else 3 if rssi < -60 else 4
    for i in range(4):
        h = 3 + i * 3
        screen.pen = (rssi_color(rssi) if not faded else MUTED) if i < level else DIM
        screen.rectangle(x + i * 4, y + 12 - h, 3, h)


def fit(text, size, max_width):
    if screen.measure_text(text, font_size=size)[0] <= max_width:
        return text
    while text and screen.measure_text(text + "...", font_size=size)[0] > max_width:
        text = text[:-1]
    return text + "..."


def age(ms):
    s = max(ms // 1000, 0)
    if s < 60:
        return "{}s".format(s)
    if s < 3600:
        return "{}m {:02d}s".format(s // 60, s % 60)
    return "{}h {:02d}m".format(s // 3600, (s // 60) % 60)


def draw_list():
    global top

    if selected < top:
        top = selected
    elif selected >= top + ROWS:
        top = selected - ROWS + 1

    if not order:
        screen.pen = ALERT if ble_error else MUTED
        text = ble_error or ("Paused" if paused else "Listening for devices...")
        w, _ = screen.measure_text(text, font_size=14)
        screen.text(text, (screen.width - w) / 2, 110, font_size=14)
        return

    now = badge.ticks
    for row in range(ROWS):
        i = top + row
        if i >= len(order):
            break
        dev = seen.get(order[i])
        if dev is None:
            continue
        y = LIST_Y + row * ROW_H
        faded = gone(dev)

        if i == selected:
            screen.pen = ROW_SEL
            screen.rectangle(0, y, screen.width, ROW_H)

        fresh = now - dev["first"]
        if fresh < NEW_FOR and not faded:
            screen.pen = color.rgb(150, 160, 255, int(255 * (1 - fresh / NEW_FOR)))
            screen.rectangle(0, y, 3, ROW_H)

        draw_bars(7, y + 2, dev["rssi"], faded)

        named = dev["name"] or dev["kind"]
        screen.pen = DIM if faded else (TEXT if named else MUTED)
        screen.text(fit(title(dev), 12, 152), 28, y + 2, font_size=12)

        who = maker(dev)
        if who:
            screen.pen = DIM if faded else MUTED
            screen.text(fit(who, 9, 92), 186, y + 4, font_size=9)

        screen.pen = DIM if faded else rssi_color(dev["rssi"])
        screen.text(str(dev["rssi"]), 284, y + 3, font_size=11)

    if len(order) > ROWS:
        track = FOOT_Y - LIST_Y
        h = max(track * ROWS // len(order), 6)
        screen.pen = DIM
        screen.rectangle(screen.width - 2, LIST_Y + (track - h) * top // (len(order) - ROWS), 2, h)


def draw_detail():
    dev = seen.get(order[selected])
    if dev is None:
        return
    now = badge.ticks
    x, y, w, h = 10, 26, screen.width - 20, 194
    screen.pen = color.rgb(14, 20, 32)
    screen.rectangle(x, y, w, h)
    screen.pen = ROW_SEL
    screen.rectangle(x, y, w, 2)

    screen.pen = TEXT if dev["name"] else MUTED
    screen.text(fit(dev["name"] or "<no name>", 16, w - 20), x + 10, y + 8, font_size=16)

    services = ", ".join(SERVICES.get(u) or "{:04X}".format(u) for u in dev["uuids"]) or "-"
    lines = (
        ("Address", "{}  {}".format(addr_text(dev["addr"]), "random" if dev["random"] else "public")),
        ("Maker", maker(dev) or "-"),
        ("Type", dev["kind"] or "-"),
        ("Services", services),
        ("Connectable", "yes" if dev["connectable"] else "no"),
        ("Signal", "{} dBm   best {}".format(dev["rssi"], dev["best"])
         + ("   tx {}".format(dev["tx"]) if dev["tx"] is not None else "")),
        ("First seen", age(now - dev["first"]) + " ago"),
        ("Last heard", ("gone, " if gone(dev) else "") + age(now - dev["last"]) + " ago"),
    )
    ly = y + 34
    for label, value in lines:
        screen.pen = MUTED
        screen.text(label, x + 10, ly, font_size=11)
        screen.pen = TEXT
        screen.text(fit(value, 11, w - 104), x + 94, ly, font_size=11)
        ly += 19


def draw_chrome():
    screen.pen = BAR
    screen.rectangle(0, 0, screen.width, TOP_H)
    screen.rectangle(0, FOOT_Y, screen.width, screen.height - FOOT_Y)

    screen.pen = TEXT
    screen.text("BLE SCAN", 6, 4, font_size=13)

    live = sum(1 for d in seen.values() if not gone(d))
    label = "{} here  {} seen".format(live, len(seen))
    if paused:
        label += "  paused"
    screen.pen = WARM if paused else (ALERT if ble_error else MUTED)
    w, _ = screen.measure_text(label, font_size=10)
    screen.text(label, screen.width - 6 - w, 6, font_size=10)

    screen.pen = MUTED
    help_text = "C back" if detail else "UP/DN move  C info  B sort:{}  A {}".format(
        SORTS[sort_index], "resume" if paused else "pause")
    screen.text(help_text, 6, FOOT_Y + 4, font_size=9)


def update():
    global selected, sort_index, paused, detail

    # re-sort on a timer even when nothing new arrived: devices age into "gone"
    absorb()
    if badge.ticks - last_sort > RESORT_EVERY:
        resort()

    if badge.pressed(BUTTON_A):
        paused = not paused
        if paused:
            stop_scan()
        else:
            start_scan()
    if order:
        if badge.pressed(BUTTON_C):
            detail = not detail
        if not detail:
            if badge.pressed(BUTTON_DOWN):
                selected = (selected + 1) % len(order)
            if badge.pressed(BUTTON_UP):
                selected = (selected - 1) % len(order)
            if badge.pressed(BUTTON_B):
                sort_index = (sort_index + 1) % len(SORTS)
                selected = 0
                resort()

    screen.pen = BG
    screen.clear()
    draw_list()
    if detail and order:
        draw_detail()
    draw_chrome()


def on_exit():
    stop_scan()
    try:
        ble.active(False)
    except OSError:
        pass


ble = bluetooth.BLE()
try:
    ble.active(True)
    ble.irq(on_irq)
    start_scan()
except OSError as e:
    ble_error = "Bluetooth didn't start ({})".format(e)

run(update)
