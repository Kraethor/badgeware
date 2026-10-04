# A replacement for the badge's secrets.py that lets it use more than one WiFi
# network. Fill in your details, then copy this file to the root of the badge's
# drive as "secrets.py".

# WiFi networks, in order of preference. The badge joins the first one it can see.
# Add or remove lines as needed; a network that isn't in range is simply skipped.
WIFI_NETWORKS = [
    ("FIRST_NETWORK_NAME", "FIRST_NETWORK_PASSWORD"),
    ("SECOND_NETWORK_NAME", "SECOND_NETWORK_PASSWORD"),
]

REGION = "eu"  # Options are us, cuba, eu, moldova, lebanon, egypt, chile, australia, nz
TIMEZONE = 0  # Offset from GMT as number of hours, i.e. 0, 1, -7 etc.

# --- no need to edit below this line ---
# The badge's WiFi code only understands one network (WIFI_SSID / WIFI_PASSWORD),
# so look at what is in range and hand it whichever listed network is there.
# If none of them is, it falls back to the first in the list.
WIFI_SSID, WIFI_PASSWORD = WIFI_NETWORKS[0]
if len(WIFI_NETWORKS) > 1:
    try:
        import network as _network
        _wlan = _network.WLAN(_network.STA_IF)
        if not _wlan.isconnected():
            _was_active = _wlan.active()
            _wlan.active(True)
            _found = False
            for _attempt in range(2):
                _seen = [_n[0].decode() for _n in _wlan.scan()]
                for _ssid, _psk in WIFI_NETWORKS:
                    if _ssid in _seen:
                        WIFI_SSID, WIFI_PASSWORD = _ssid, _psk
                        _found = True
                        break
                if _found:
                    break
            if not _was_active:
                _wlan.active(False)
    except Exception:  # noqa: BLE001 - never let a failed scan stop an app loading
        pass
