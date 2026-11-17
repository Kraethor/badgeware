import network

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

ui_font = font.load("/system/assets/fonts/MonaSans-Medium.af")
screen.font = ui_font

SCAN_GAP = 2000     # ms between the end of one scan and the start of the next
NEW_FOR = 6000      # ms a network stays marked as new
STALE_AFTER = 3     # scans missed before a network is shown as gone
MAX_SEEN = 250      # networks remembered; the longest unseen are dropped first

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
NEW = color.rgb(120, 230, 255)
OPEN = color.rgb(255, 200, 70)
ALERT = color.rgb(255, 90, 70)

SORTS = ("newest", "latest", "signal", "channel")

seen = {}           # bssid bytes -> record dict
order = []          # bssids in the current sort order
sort_index = 0
selected = 0
top = 0
paused = False
detail = False
scans = 0
scanning = False    # set on the frame before a scan so "scanning" gets drawn
next_scan = 0
scan_error = None

wlan = network.WLAN(network.STA_IF)
wlan.active(True)


def security(flags):
    # The cyw43 driver in firmware v3.1.1 reports three bits: 4 = RSN element
    # (WPA2, but also WPA3 or enterprise: it doesn't say which), 2 = WPA element,
    # 1 = privacy bit (set for any encrypted network). WEP is the privacy bit alone.
    # Newer drivers report CYW43_AUTH_FLAG_* values instead; read those if present.
    if flags == 0:
        return "OPEN"
    if flags > 0xFF:
        eap = "-EAP" if flags & 0x02000000 else ""
        if flags & 0x01000000:
            return ("WPA2/3" if flags & 0x00400000 else "WPA3") + eap
        if flags & 0x00400000:
            return "WPA2" + eap
        if flags & 0x00200000:
            return "WPA" + eap
    if flags & 4 and flags & 2:
        return "WPA/WPA2"
    if flags & 4:
        return "WPA2"
    if flags & 2:
        return "WPA"
    return "WEP"


def ssid_text(raw):
    if not raw or raw.count(b"\x00") == len(raw):
        return None
    try:
        return raw.decode()
    except UnicodeError:
        return "".join(chr(b) if 32 <= b < 127 else "?" for b in raw)


def mac_text(bssid):
    return ":".join("{:02X}".format(b) for b in bssid)


def do_scan():
    global scans, scan_error

    try:
        results = wlan.scan()
    except OSError as e:
        scan_error = "scan failed ({})".format(e)
        return
    scan_error = None
    scans += 1
    now = badge.ticks

    for raw_ssid, bssid, channel, rssi, auth, _ in results:
        net = seen.get(bssid)
        if net is None:
            net = {
                "ssid": ssid_text(raw_ssid),
                "bssid": bssid,
                "first": now,
                "best": rssi,
            }
            seen[bssid] = net
        net["channel"] = channel
        net["rssi"] = rssi
        net["best"] = max(net["best"], rssi)
        net["sec"] = security(auth)
        net["last"] = now
        net["scan"] = scans

    if len(seen) > MAX_SEEN:
        oldest = sorted(seen.values(), key=lambda n: n["last"])
        for net in oldest[:len(seen) - MAX_SEEN]:
            del seen[net["bssid"]]

    resort()


def gone(net):
    return scans - net["scan"] >= STALE_AFTER


def resort():
    global order, selected

    keep = order[selected] if order and selected < len(order) else None
    nets = list(seen.values())
    mode = SORTS[sort_index]
    if mode == "newest":
        nets.sort(key=lambda n: -n["first"])
    elif mode == "latest":
        # most recently heard first; networks heard in the same scan by signal
        nets.sort(key=lambda n: (-n["last"], -n["rssi"]))
    elif mode == "signal":
        nets.sort(key=lambda n: (gone(n), -n["rssi"]))
    else:
        nets.sort(key=lambda n: (n["channel"], -n["rssi"]))
    order = [n["bssid"] for n in nets]
    # in "newest" the cursor stays at the top so new finds land under it;
    # otherwise it follows the network it was on
    if mode != "newest" and keep in order:
        selected = order.index(keep)
    selected = min(selected, max(len(order) - 1, 0))


def rssi_color(rssi, alpha=255):
    # red when weak, through yellow, to green when strong
    t = min(max((rssi + 90) / 40, 0), 1)
    if t < 0.5:
        return color.rgb(255, int(90 + 330 * t), 70, alpha)
    return color.rgb(int(255 - 330 * (t - 0.5)), 255, int(70 + 60 * (t - 0.5)), alpha)


def draw_bars(x, y, rssi, faded):
    level = 0 if rssi < -85 else 1 if rssi < -75 else 2 if rssi < -65 else 3 if rssi < -55 else 4
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
        screen.pen = MUTED
        text = scan_error or "Looking for networks..."
        w, _ = screen.measure_text(text, font_size=14)
        screen.text(text, (screen.width - w) / 2, 110, font_size=14)
        return

    now = badge.ticks
    for row in range(ROWS):
        i = top + row
        if i >= len(order):
            break
        net = seen[order[i]]
        y = LIST_Y + row * ROW_H
        faded = gone(net)

        if i == selected:
            screen.pen = ROW_SEL
            screen.rectangle(0, y, screen.width, ROW_H)

        fresh = now - net["first"]
        if fresh < NEW_FOR and not faded:
            # a bar down the left edge that fades out as the find gets older
            screen.pen = color.rgb(120, 230, 255, int(255 * (1 - fresh / NEW_FOR)))
            screen.rectangle(0, y, 3, ROW_H)

        draw_bars(7, y + 2, net["rssi"], faded)

        name = net["ssid"]
        screen.pen = DIM if faded else (MUTED if name is None else TEXT)
        screen.text(fit(name or "<hidden>", 12, 168), 28, y + 2, font_size=12)

        screen.pen = DIM if faded else (OPEN if net["sec"] == "OPEN" else MUTED)
        screen.text(net["sec"], 202, y + 4, font_size=9)

        screen.pen = DIM if faded else MUTED
        screen.text("{:>2}".format(net["channel"]), 256, y + 3, font_size=11)
        screen.pen = DIM if faded else rssi_color(net["rssi"])
        screen.text(str(net["rssi"]), 282, y + 3, font_size=11)

    # scroll position
    if len(order) > ROWS:
        track = FOOT_Y - LIST_Y
        h = max(track * ROWS // len(order), 6)
        screen.pen = DIM
        screen.rectangle(screen.width - 2, LIST_Y + (track - h) * top // (len(order) - ROWS), 2, h)


def draw_detail():
    net = seen[order[selected]]
    now = badge.ticks
    x, y, w, h = 14, 34, screen.width - 28, 176
    screen.pen = color.rgb(14, 20, 32)
    screen.rectangle(x, y, w, h)
    screen.pen = ROW_SEL
    screen.rectangle(x, y, w, 2)

    screen.pen = TEXT if net["ssid"] else MUTED
    screen.text(fit(net["ssid"] or "<hidden network>", 16, w - 20), x + 10, y + 10, font_size=16)

    lines = (
        ("BSSID", mac_text(net["bssid"])),
        ("Security", net["sec"]),
        ("Channel", "{}  (2.4 GHz)".format(net["channel"])),
        ("Signal", "{} dBm   best {} dBm".format(net["rssi"], net["best"])),
        ("First seen", age(now - net["first"]) + " ago"),
        ("Last seen", "gone, " + age(now - net["last"]) + " ago" if gone(net)
         else age(now - net["last"]) + " ago"),
    )
    ly = y + 38
    for label, value in lines:
        screen.pen = MUTED
        screen.text(label, x + 10, ly, font_size=11)
        screen.pen = OPEN if value == "OPEN" else TEXT
        screen.text(value, x + 90, ly, font_size=11)
        ly += 20


def draw_chrome():
    screen.pen = BAR
    screen.rectangle(0, 0, screen.width, TOP_H)
    screen.rectangle(0, FOOT_Y, screen.width, screen.height - FOOT_Y)

    screen.pen = TEXT
    screen.text("WIFI SCAN", 6, 4, font_size=13)

    live = sum(1 for n in seen.values() if not gone(n))
    if paused:
        status, pen = "paused", OPEN
    elif scan_error and order:
        status, pen = "scan failed", ALERT
    elif scanning:
        status, pen = "scanning...", NEW
    else:
        status, pen = "", MUTED
    label = "{} here  {} seen  {}".format(live, len(seen), status).rstrip()
    screen.pen = pen if status else MUTED
    w, _ = screen.measure_text(label, font_size=10)
    screen.text(label, screen.width - 6 - w, 6, font_size=10)

    screen.pen = MUTED
    help_text = "C back" if detail else "UP/DN move  C info  B sort:{}  A {}".format(
        SORTS[sort_index], "resume" if paused else "pause")
    screen.text(help_text, 6, FOOT_Y + 4, font_size=9)


def update():
    global selected, sort_index, paused, detail, scanning, next_scan

    if scanning:
        # "scanning" was drawn last frame; the scan blocks for a couple of seconds
        do_scan()
        scanning = False
        next_scan = badge.ticks + SCAN_GAP
    elif not paused and badge.ticks >= next_scan:
        scanning = True

    if badge.pressed(BUTTON_A):
        paused = not paused
        scanning = False
        next_scan = badge.ticks
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
    # the radio is left on: the shared wifi module may hold the same interface
    # for the next app, and switching it off under it stalls that app's connect
    pass


run(update)
