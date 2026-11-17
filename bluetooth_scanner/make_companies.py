"""Builds bluetooth_scanner/assets/companies.bin, the table the badge uses to
turn the manufacturer ID in a Bluetooth advertisement into a company name.

It downloads the Bluetooth SIG's list of company identifiers, so it needs an
internet connection but no extra packages. Run it on your computer, then copy
the bluetooth_scanner folder to the badge as usual:

    python bluetooth_scanner/make_companies.py

The generated file is not kept in this repository; the list belongs to the
Bluetooth SIG. Without it the app still works, naming a handful of common
manufacturers and showing the rest as a hex ID.

File format: fixed 32-byte records sorted by ID, so the badge can binary-search
the file without loading it. Each record is the ID as 2 bytes little-endian,
then the name as UTF-8, padded with zero bytes to 30.
"""
import re
import struct
import urllib.request
from pathlib import Path

URL = ("https://bitbucket.org/bluetooth-SIG/public/raw/main/"
       "assigned_numbers/company_identifiers/company_identifiers.yaml")
OUT = Path(__file__).parent / "assets" / "companies.bin"
NAME_BYTES = 30

# legal suffixes that only take up room on a 320-pixel screen
SUFFIX = re.compile(
    r"[,\s]+(inc|ltd|llc|limited|corp|corporation|co|gmbh|ag|sa|s\.?a\.?s|b\.?v|ab|as|asa|"
    r"oy|plc|pty|s\.?r\.?l|s\.?p\.?a|kg|srl|spa|sas|nv|bv|a/s|co\.,? ltd)\.?$",
    re.IGNORECASE)


def tidy(name):
    name = name.strip()
    while True:
        shorter = SUFFIX.sub("", name).strip(" ,")
        if shorter == name or not shorter:
            return name
        name = shorter


def clip(name):
    raw = name.encode("utf-8")
    while len(raw) > NAME_BYTES:
        name = name[:-1]
        raw = name.encode("utf-8")
    return raw


def main():
    with urllib.request.urlopen(URL, timeout=30) as r:
        text = r.read().decode("utf-8")

    pairs = re.findall(r"value:\s*0x([0-9A-Fa-f]{4})\s*\n\s*name:\s*(['\"])(.*?)\2\s*$",
                       text, re.MULTILINE)
    companies = {}
    for hex_id, _, name in pairs:
        companies[int(hex_id, 16)] = tidy(name.replace("''", "'"))
    if len(companies) < 1000:
        raise SystemExit("only parsed {} companies; has the list's format changed?".format(len(companies)))

    OUT.parent.mkdir(exist_ok=True)
    with open(OUT, "wb") as f:
        for cid in sorted(companies):
            f.write(struct.pack("<H", cid) + clip(companies[cid]).ljust(NAME_BYTES, b"\0"))
    print("wrote {} companies to {} ({} bytes)".format(len(companies), OUT, OUT.stat().st_size))


if __name__ == "__main__":
    main()
