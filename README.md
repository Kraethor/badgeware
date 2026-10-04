# badgeware

Apps for the [Pimoroni Badgeware Tufty 2350](https://shop.pimoroni.com/products/tufty-2350)
badge. Each one pulls live data over WiFi and draws it on the badge's 320x240 screen.

Written and tested on Tufty firmware v3.1.1.

## Apps

### Planes Overhead

A radar scope of the aircraft flying near you right now: a rotating sweep, range
rings, and a marker for each aircraft pointing along its heading. A side panel
shows the selected aircraft's callsign, type, altitude, speed, distance, bearing
and heading.

| Button | Action |
|---|---|
| A / C | Step through aircraft, nearest first |
| UP / DOWN | Change range (10, 25, 50, 100 nm) |
| B | Toggle callsign labels |

- Aircraft positions come from [adsb.lol](https://adsb.lol) every 20 seconds.
  Between fetches each marker keeps moving along its last reported track.
- The badge works out roughly where it is from its internet address, using
  [ip-api.com](https://ip-api.com). To pin an exact position instead, add
  `LATITUDE` and `LONGITUDE` to `secrets.py` on the badge.
- adsb.lol asks every client to identify itself with a contact detail. **Change
  the `HEADERS` line near the top of `planes_overhead/__init__.py` to your own
  contact before you use it.**

### Earthquakes

Recent earthquakes from the [USGS](https://earthquake.usgs.gov/earthquakes/feed/)
plotted on a world map, sized and coloured by magnitude. The bar underneath shows
the selected quake's magnitude, place, age and depth.

![Earthquakes running on a Tufty 2350](docs/earthquakes.png)

| Button | Action |
|---|---|
| A / C | Step through quakes, newest first |
| UP / DOWN | Zoom in on the selected quake |
| B | Switch feed (M2.5+ past day, M4.5+ past week, significant past month) |

- The feed refreshes every five minutes.
- The map is the `world.geo.json` that ships with the stock firmware.

## Installing

1. Set your WiFi details in `secrets.py` on the badge, if you haven't already.
2. Put the badge into disk mode (double-press RESET).
3. Copy the app's folder (`planes_overhead` or `earthquakes`) into `apps` on the badge.
4. Eject the drive and wait for it to finish, then press RESET.

Always eject before resetting or unplugging. The badge's drive is easily
corrupted if it disappears while the computer is still writing to it.

## Icons

`make_app_icons.py` draws the 24x24 launcher icons from character grids, so they
can be edited pixel by pixel. It needs Pillow (`pip install pillow`).

## Data sources

Check each provider's terms before building on these apps.

- [adsb.lol](https://adsb.lol) for aircraft positions
- [ip-api.com](https://ip-api.com) for approximate location (free for non-commercial use)
- [USGS Earthquake Hazards Program](https://earthquake.usgs.gov/earthquakes/feed/) for earthquakes

## License

GPL-3.0. See [LICENSE](LICENSE).
