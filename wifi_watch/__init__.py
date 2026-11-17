import json
import math
import os
import socket

import network

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

ui_font = font.load("/system/assets/fonts/MonaSans-Medium.af")
screen.font = ui_font

STATE_FILE = "/state/wifi_watch.json"

SCAN_GAP = 2000         # ms between one radio job and the next
NET_CHECK_EVERY = 60000 # ms between captive portal / DNS checks while connected
RECONNECT_AFTER = 5000  # ms to wait before rejoining after a drop
DROP_WINDOW = 300000    # ms over which connection drops are counted
DROPS_CAUTION = 3
DROPS_ALERT = 6
STRONGER_BY = 25        # dB above the learned best before a known AP is "too strong"
FLOOD_MIN = 25          # extra networks in one scan before a spike counts
FLOOD_NEW = 20          # brand-new networks in one scan before that counts
RECENT_SCANS = 2        # a network counts as present if heard this many scans back
LEARN_SCANS = 15        # learning takes every AP heard this many scans back (~2 min),
                        # so distant APs that are only heard now and then are included
MAX_SEEN = 300

PORTAL_HOST = "connectivitycheck.gstatic.com"
PORTAL_PATH = "/generate_204"
DNS_NAMES = ("connectivitycheck.gstatic.com", "example.com")

OFF, OK, CAUTION, ALERT = -1, 0, 1, 2

BG = color.rgb(8, 12, 20)
BAR = color.rgb(4, 6, 12)
PANEL = color.rgb(14, 20, 32)
TEXT = color.rgb(226, 232, 240)
MUTED = color.rgb(130, 150, 172)
DIM = color.rgb(70, 82, 98)
LEVEL_COLORS = {
    OFF: color.rgb(70, 82, 98),
    OK: color.rgb(70, 200, 120),
    CAUTION: color.rgb(255, 190, 60),
    ALERT: color.rgb(255, 80, 70),
}
LEVEL_WORDS = {OK: "ALL CLEAR", CAUTION: "CAUTION", ALERT: "ALERT"}


# ---------------------------------------------------------------- settings

try:
    import secrets
    if getattr(secrets, "WIFI_NETWORKS", None):
        TRUSTED = {s: p for s, p in secrets.WIFI_NETWORKS if s}
    else:
        TRUSTED = {secrets.WIFI_SSID: secrets.WIFI_PASSWORD} if getattr(secrets, "WIFI_SSID", "") else {}
    JOIN_SSID = getattr(secrets, "WIFI_SSID", "") or None
    JOIN_PSK = getattr(secrets, "WIFI_PASSWORD", "")
except ImportError:
    TRUSTED = {}
    JOIN_SSID = None
    JOIN_PSK = ""
# placeholder names from the templates aren't real networks
TRUSTED = {s: p for s, p in TRUSTED.items() if "NETWORK_NAME" not in s}
if JOIN_SSID not in TRUSTED:
    JOIN_SSID = None

baseline = {}       # ssid -> {bssid hex: {"sec", "ch", "best"}}


def load_baseline():
    global baseline
    try:
        with open(STATE_FILE) as f:
            data = json.loads(f.read())
        baseline = data.get("trusted", {})
    except (OSError, ValueError):
        baseline = {}
    # entries saved before raw security flags were stored can't be trusted:
    # their labels came from a decoder that misread WPA2 as WEP
    for ssid in list(baseline):
        if any("flags" not in k for k in baseline[ssid].values()):
            del baseline[ssid]


def save_baseline():
    try:
        os.stat("/state")
    except OSError:
        os.mkdir("/state")
    with open(STATE_FILE, "w") as f:
        f.write(json.dumps({"trusted": baseline}))


# ---------------------------------------------------------------- helpers

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


def weak(sec):
    return sec in ("OPEN", "WEP")


def ssid_text(raw):
    if not raw or raw.count(b"\x00") == len(raw):
        return None
    try:
        return raw.decode()
    except UnicodeError:
        return "".join(chr(b) if 32 <= b < 127 else "?" for b in raw)


def hexmac(bssid):
    return ":".join("{:02X}".format(b) for b in bssid)


def short_mac(mac):
    return mac[-8:]


def random_ssid():
    # lowercase letters and digits that no real network will be called
    chars = "abcdefghijkmnpqrstuvwxyz23456789"
    return "".join(chars[b % len(chars)] for b in os.urandom(12))


def age(ms):
    s = max(ms // 1000, 0)
    if s < 60:
        return "{}s".format(s)
    if s < 3600:
        return "{}m".format(s // 60)
    return "{}h {:02d}m".format(s // 3600, (s // 60) % 60)


def private_ip(ip):
    try:
        a, b = [int(x) for x in ip.split(".")[:2]]
    except ValueError:
        return False
    return (a == 10 or a == 127 or (a == 172 and 16 <= b <= 31) or (a == 192 and b == 168)
            or (a == 169 and b == 254) or (a == 100 and 64 <= b <= 127))


# ---------------------------------------------------------------- checks

class Check:
    def __init__(self, name, text):
        self.name = name
        self.level = OFF
        self.text = text
        self.worst = OFF
        self.worst_text = ""
        self.worst_at = 0
        self.last_warning = None

    def set(self, level, text):
        self.level = level
        self.text = text
        if level >= CAUTION:
            if text != self.last_warning:
                add_history(level, self.name, text)
                self.last_warning = text
            if level >= self.worst:
                self.worst = level
                self.worst_text = text
                self.worst_at = badge.ticks

    def shown(self):
        # latched: a past warning stays on screen until cleared with A
        if self.worst > self.level and self.worst >= CAUTION:
            return self.worst, "{} ({} ago)".format(self.worst_text, age(badge.ticks - self.worst_at))
        return self.level, self.text

    def clear(self):
        # forget past warnings; anything still happening shows again at once
        self.worst = OFF
        self.worst_text = ""
        self.last_warning = None


karma = Check("Fake-network probe", "waiting for first probe")
downgrade = Check("Security downgrade", "waiting for first scan")
twin = Check("Evil twin", "waiting for first scan")
flood = Check("Beacon flood", "waiting for first scans")
drops = Check("Connection drops", "")
portal = Check("Portal / DNS", "")
CHECKS = (karma, downgrade, twin, flood, drops, portal)

history = []        # (ticks, level, check name, text), newest first, RAM only


def add_history(level, name, text):
    history.insert(0, (badge.ticks, level, name, text))
    del history[50:]


# ---------------------------------------------------------------- radio state

wlan = network.WLAN(network.STA_IF)
wlan.active(True)

seen = {}           # bssid bytes -> {"ssid", "sec", "ch", "rssi", "scan"}
scans = 0
counts = []         # networks heard per scan, most recent last
probes = 0
probe_answers = 0

was_connected = False
drop_times = []
next_join = 0
join_started = False
joining_until = 0       # radio jobs wait while a join is in progress
next_net_check = 0

job = None          # radio job shown as running this frame, run on the next
next_job_at = 0
job_cycle = 0
learn_armed_until = 0
message = None
message_until = 0
page = "checks"
history_top = 0


def present():
    return [n for n in seen.values() if scans - n["scan"] < RECENT_SCANS]


def run_scan():
    global scans

    try:
        results = wlan.scan()
    except OSError:
        return
    scans += 1
    new_here = 0
    for raw, bssid, ch, rssi, auth, _ in results:
        net = seen.get(bssid)
        if net is None:
            net = {"ssid": ssid_text(raw)}
            seen[bssid] = net
            if scans > 1:
                new_here += 1
        net["flags"] = auth
        net["sec"] = security(auth)
        net["ch"] = ch
        net["rssi"] = rssi
        net["best"] = max(net.get("best", rssi), rssi)
        net["scan"] = scans
    if len(seen) > MAX_SEEN:
        for bssid in sorted(seen, key=lambda b: seen[b]["scan"])[:len(seen) - MAX_SEEN]:
            del seen[bssid]
    counts.append(len(results))
    del counts[:-8]

    check_downgrade()
    check_twin()
    check_flood(len(results), new_here)


def run_probe():
    # ask for a network that can't exist; only a rogue AP that says yes to
    # every name (KARMA / Pineapple style) will answer
    global probes, probe_answers

    name = random_ssid()
    try:
        results = wlan.scan(ssid=name.encode())
    except OSError:
        return
    probes += 1
    liars = [r for r in results if r[0] == name.encode()]
    if liars:
        probe_answers += 1
        r = liars[0]
        karma.set(ALERT, "{} answered made-up name '{}' (ch {})".format(hexmac(r[1]), name, r[2]))
    else:
        karma.set(OK, "no answers to {} made-up names".format(probes))


def check_downgrade():
    by_ssid = {}
    for n in present():
        if n["ssid"]:
            by_ssid.setdefault(n["ssid"], []).append(n)
    worst, text = OK, "no open copies of secured networks"
    for ssid, nets in by_ssid.items():
        secs = set(n["sec"] for n in nets)
        if any(weak(s) for s in secs) and any(not weak(s) for s in secs):
            bad = [n for n in nets if weak(n["sec"])][0]
            worst, text = ALERT, "'{}' is also broadcast {} on ch {}".format(ssid, bad["sec"], bad["ch"])
            break
        if ssid in TRUSTED and TRUSTED[ssid] and all(weak(s) for s in secs):
            worst, text = ALERT, "your '{}' is showing as {}".format(ssid, nets[0]["sec"])
            break
    downgrade.set(worst, text)


def check_twin():
    if not TRUSTED:
        twin.set(OFF, "no networks in secrets.py to watch")
        return
    here = {}
    for bssid, n in seen.items():
        if n["ssid"] in TRUSTED and scans - n["scan"] < RECENT_SCANS:
            here.setdefault(n["ssid"], []).append((hexmac(bssid), n))
    if not here:
        twin.set(OFF, "none of your networks in range")
        return

    unlearned = [s for s in here if s not in baseline]
    level, text = OK, ""
    for ssid, aps in here.items():
        known = baseline.get(ssid)
        if not known:
            continue
        known_flags = set(k["flags"] for k in known.values())
        for mac, n in aps:
            k = known.get(mac)
            if k is None:
                if n["flags"] not in known_flags:
                    level, text = ALERT, "'{}' from unknown AP {} as {}".format(ssid, short_mac(mac), n["sec"])
                elif level < CAUTION:
                    level, text = CAUTION, "'{}' from unknown AP {} ch {}".format(ssid, short_mac(mac), n["ch"])
            elif n["flags"] != k["flags"]:
                level, text = ALERT, "known AP {} changed {} -> {}".format(
                    short_mac(mac), security(k["flags"]), n["sec"])
            elif n["rssi"] > k["best"] + STRONGER_BY and level < CAUTION:
                level, text = CAUTION, "known AP {} much stronger than usual ({} dBm)".format(short_mac(mac), n["rssi"])
        if level == ALERT:
            break
    if level == OK:
        if unlearned and len(unlearned) == len(here):
            twin.set(OFF, "'{}' not learned yet - press B".format(unlearned[0]))
            return
        n_aps = sum(len(a) for s, a in here.items() if s in baseline)
        text = "{} known AP{} for {}".format(n_aps, "" if n_aps == 1 else "s",
                                             ", ".join(s for s in here if s in baseline))
        if unlearned:
            text += "; '{}' not learned".format(unlearned[0])
    twin.set(level, text)


def check_flood(count, new_here):
    if len(counts) < 4:
        flood.set(OK, "{} networks, learning normal level".format(count))
        return
    usual = sorted(counts[:-1])[len(counts[:-1]) // 2]
    if count > max(usual * 2, usual + FLOOD_MIN):
        flood.set(CAUTION, "spike: {} networks, usually {}".format(count, usual))
    elif new_here >= FLOOD_NEW:
        flood.set(CAUTION, "{} new networks appeared in one scan".format(new_here))
    else:
        flood.set(OK, "{} networks, usual ~{}".format(count, usual))


def learn():
    # adds to what was learned before, so learning in a few rooms (or at home
    # and at work) builds up the full set of access points
    global message, message_until
    learned = []
    for ssid, pw in TRUSTED.items():
        aps = baseline.get(ssid, {})
        added = 0
        for bssid, n in seen.items():
            if n["ssid"] != ssid or scans - n["scan"] >= LEARN_SCANS:
                continue
            if pw and weak(n["sec"]):
                continue    # never learn an open copy of a secured network
            mac = hexmac(bssid)
            if mac not in aps:
                added += 1
            best = max(aps[mac]["best"], n["best"]) if mac in aps else n["best"]
            aps[mac] = {"flags": n["flags"], "sec": n["sec"], "ch": n["ch"], "best": best}
        if aps:
            baseline[ssid] = aps
            learned.append("{} +{} ({})".format(ssid, added, len(aps)))
    if learned:
        save_baseline()
        message = "Trusted APs: " + ", ".join(learned)
        # a new baseline makes the earlier evil-twin warning stale: drop the latch
        # so what shows now is judged against what was just learned
        twin.clear()
        check_twin()
    else:
        message = "None of your networks heard recently"
    message_until = badge.ticks + 5000


def forget():
    global baseline, message, message_until
    baseline = {}
    save_baseline()
    twin.clear()
    check_twin()
    message = "Forgot all learned access points"
    message_until = badge.ticks + 4000


# ---------------------------------------------------------------- connection

def watch_connection():
    global was_connected, next_join, join_started, joining_until

    if JOIN_SSID is None:
        drops.set(OFF, "no network in secrets.py to join")
        portal.set(OFF, "needs a connection")
        return

    now = badge.ticks
    connected = wlan.isconnected()
    if was_connected and not connected:
        drop_times.append(now)
        next_join = now + RECONNECT_AFTER
        join_started = False
    was_connected = connected
    while drop_times and now - drop_times[0] > DROP_WINDOW:
        drop_times.pop(0)

    n = len(drop_times)
    if connected:
        level = ALERT if n >= DROPS_ALERT else CAUTION if n >= DROPS_CAUTION else OK
        drops.set(level, "joined '{}', {} drop{} in 5 min".format(JOIN_SSID, n, "" if n == 1 else "s"))
    else:
        if not join_started and now >= next_join:
            try:
                wlan.connect(JOIN_SSID, JOIN_PSK)
            except OSError:
                pass
            join_started = True
            next_join = now + 30000     # give up on this attempt after 30 s
            joining_until = now + 15000
        elif join_started and now >= next_join:
            join_started = False
        level = ALERT if n >= DROPS_ALERT else CAUTION if n >= DROPS_CAUTION else OFF
        status = wlan.status()
        why = {-3: "wrong password?", -2: "not in range"}.get(status, "joining...")
        drops.set(level, "{} drops in 5 min, rejoining".format(n) if n else "'{}': {}".format(JOIN_SSID, why))
        if portal.level != OFF or not portal.text:
            portal.set(OFF, "needs a connection")


def check_portal_dns():
    # DNS first: a well-known name answering with a private address
    sinkholed = []
    for name in DNS_NAMES:
        try:
            ip = socket.getaddrinfo(name, 80)[0][-1][0]
        except (OSError, IndexError):
            portal.set(CAUTION, "DNS lookup for {} failed".format(name))
            return
        ip = str(ip)
        if ip == "0.0.0.0":
            sinkholed.append(name)
        elif private_ip(ip):
            portal.set(ALERT, "DNS: {} -> private {}".format(name, ip))
            return

    # then the connectivity check: anything but an empty 204 is a portal or proxy
    s = socket.socket()
    try:
        s.settimeout(6)
        s.connect(socket.getaddrinfo(PORTAL_HOST, 80)[0][-1])
        s.send(b"GET " + PORTAL_PATH.encode() + b" HTTP/1.0\r\nHost: " + PORTAL_HOST.encode()
               + b"\r\nUser-Agent: tufty-wifi-watch\r\n\r\n")
        line = s.readline() if hasattr(s, "readline") else s.recv(64)
        code = int(line.split()[1])
    except (OSError, ValueError, IndexError):
        portal.set(CAUTION, "connectivity check didn't complete")
        return
    finally:
        s.close()

    if code != 204:
        portal.set(CAUTION, "connectivity check got HTTP {} (portal or proxy)".format(code))
    elif sinkholed:
        portal.set(CAUTION, "DNS blocks {}".format(sinkholed[0]))
    else:
        portal.set(OK, "DNS and connectivity check clean")


# ---------------------------------------------------------------- drawing

def fit(text, size, max_width):
    if screen.measure_text(text, font_size=size)[0] <= max_width:
        return text
    while text and screen.measure_text(text + "...", font_size=size)[0] > max_width:
        text = text[:-1]
    return text + "..."


def overall():
    levels = [c.shown()[0] for c in CHECKS]
    return max(OK, max(levels))


def draw_checks():
    level = overall()
    col = LEVEL_COLORS[level]

    # status panel
    screen.pen = PANEL
    screen.rectangle(0, 24, screen.width, 46)
    screen.pen = col
    screen.rectangle(0, 24, 6, 46)
    screen.text(LEVEL_WORDS[level], 16, 30, font_size=24)
    screen.pen = MUTED
    here = len(present())
    info = "{} networks here".format(here)
    w, _ = screen.measure_text(info, font_size=10)
    screen.text(info, screen.width - 8 - w, 32, font_size=10)
    info = "{} scans, {} probes".format(scans, probes)
    w, _ = screen.measure_text(info, font_size=10)
    screen.text(info, screen.width - 8 - w, 48, font_size=10)

    y = 74
    for c in CHECKS:
        lvl, text = c.shown()
        screen.pen = LEVEL_COLORS[lvl]
        screen.shape(shape.circle(11, y + 11, 5))
        screen.pen = TEXT if lvl != OFF else MUTED
        screen.text(c.name, 22, y + 1, font_size=11)
        screen.pen = LEVEL_COLORS[lvl] if lvl >= CAUTION else (MUTED if lvl == OK else DIM)
        screen.text(fit(text, 9, screen.width - 28), 22, y + 13, font_size=9)
        y += 24


def draw_history():
    global history_top
    screen.pen = TEXT
    screen.text("Warnings this session", 8, 28, font_size=13)
    if not history:
        screen.pen = MUTED
        screen.text("Nothing yet", 8, 54, font_size=11)
        return
    rows = 12
    history_top = min(history_top, max(len(history) - rows, 0))
    y = 50
    for when, lvl, name, text in history[history_top:history_top + rows]:
        screen.pen = LEVEL_COLORS[lvl]
        screen.shape(shape.circle(10, y + 6, 3))
        screen.pen = MUTED
        screen.text(age(badge.ticks - when), 18, y, font_size=9)
        screen.pen = TEXT
        screen.text(fit(name + ": " + text, 9, screen.width - 66), 58, y, font_size=9)
        y += 14


def draw_chrome():
    screen.pen = BAR
    screen.rectangle(0, 0, screen.width, 22)
    screen.rectangle(0, 222, screen.width, 18)

    screen.pen = TEXT
    screen.text("WIFI WATCH", 6, 4, font_size=13)
    label = {"scan": "scanning...", "probe": "probing...", "net": "checking DNS..."}.get(job, "")
    if label:
        screen.pen = LEVEL_COLORS[OK]
        w, _ = screen.measure_text(label, font_size=10)
        screen.text(label, screen.width - 6 - w, 6, font_size=10)

    if message and badge.ticks < message_until:
        screen.pen = TEXT
        footer = message
    elif badge.ticks < learn_armed_until:
        screen.pen = LEVEL_COLORS[CAUTION]
        footer = ("Press B again to forget ALL learned APs" if page == "history"
                  else "Press B again to trust APs heard in the last ~2 min")
    elif page == "history":
        screen.pen = MUTED
        footer = "UP/DN scroll   B forget learned APs   C back"
    else:
        screen.pen = MUTED
        footer = "A clear warnings   B learn trusted APs   C history"
    screen.text(fit(footer, 9, screen.width - 12), 6, 226, font_size=9)


def lights():
    level = overall()
    if level == ALERT:
        badge.caselights(0.5 + 0.5 * math.sin(badge.ticks / 150))
    elif level == CAUTION:
        badge.caselights(0.15)
    else:
        badge.caselights(0)


# ---------------------------------------------------------------- main loop

def update():
    global job, next_job_at, job_cycle, next_net_check, learn_armed_until, page, history_top

    # a job announced last frame runs now, so its label was on screen while it blocks
    if job == "scan":
        run_scan()
    elif job == "probe":
        run_probe()
    elif job == "net":
        check_portal_dns()
        next_net_check = badge.ticks + NET_CHECK_EVERY
    if job:
        job = None
        next_job_at = badge.ticks + SCAN_GAP

    watch_connection()

    joining = join_started and not wlan.isconnected() and badge.ticks < joining_until
    if badge.ticks >= next_job_at and job is None and not joining:
        if JOIN_SSID and wlan.isconnected() and badge.ticks >= next_net_check:
            job = "net"
        else:
            job = "probe" if job_cycle % 2 else "scan"
            job_cycle += 1

    if badge.pressed(BUTTON_A):
        for c in CHECKS:
            c.clear()
    if badge.pressed(BUTTON_B):
        if badge.ticks < learn_armed_until:
            learn_armed_until = 0
            if page == "history":
                forget()
            else:
                learn()
        else:
            learn_armed_until = badge.ticks + 3000
    if badge.pressed(BUTTON_C):
        page = "history" if page == "checks" else "checks"
        history_top = 0
        learn_armed_until = 0   # a half-done B press doesn't carry across pages
    if page == "history":
        if badge.pressed(BUTTON_DOWN):
            history_top += 1
        if badge.pressed(BUTTON_UP):
            history_top = max(history_top - 1, 0)

    screen.pen = BG
    screen.clear()
    if page == "checks":
        draw_checks()
    else:
        draw_history()
    draw_chrome()
    lights()


def on_exit():
    badge.caselights(0)


load_baseline()
run(update)
