import math

badge.mode(HIRES | VSYNC)
screen.antialias = image.X2

CX = screen.width / 2

# details to be shown on the badge
id_name = "Your Name"
id_role = "Job title"

# see the 'assets/socials' folder to see what's supported
id_socials = {"bluesky": {"icon": None, "handle": "your-handle"},
              "instagram": {"icon": None, "handle": "your-handle"},
              "github": {"icon": None, "handle": "your-handle"},
              "discord": {"icon": None, "handle": "your-handle"}
              }

# where the QR code on the last page points, and the heading above it
qr_url = "https://github.com/" + id_socials.get("github", {}).get("handle", "")
qr_title = "GitHub"

# load in the social icons
for key in id_socials.keys():
    id_socials[key]["icon"] = image.load(f"assets/socials/{key}.png")

# the logo art: full strength for the front, dimmed behind the other pages
# (make_assets.py builds both from your own image)
front_bg = image.load("assets/bg.png")
dim_bg = image.load("assets/bg_dim.png")

ui_font = font.load("/system/assets/fonts/MonaSans-Medium.af")
screen.font = ui_font

# theme colours
STEEL = color.rgb(222, 230, 242)
ICE = color.rgb(120, 190, 255)
GLOW = color.rgb(40, 120, 255)
SHADOW = color.rgb(0, 6, 20, 200)
PLATE = color.rgb(6, 10, 22, 165)
PANEL = color.rgb(8, 16, 36, 190)

PAGE_FRONT = 0
PAGE_LINKS = 1
PAGE_QR = 2
PAGE_COUNT = 3
page = PAGE_FRONT


# image.qr() needs firmware v3.1.0 or newer
qr_code = image.qr(qr_url, image.QR_MEDIUM, 2)

# layout of the links page, worked out once from the number of accounts
TITLE_H = 34
links_gap = 6
links_count = max(1, len(id_socials))
links_row_h = min(44, (screen.height - TITLE_H - 8 - links_gap * (links_count - 1)) // links_count)
links_icon = 32 if links_row_h >= 38 else 16
links_rows = []
for i in range(len(id_socials)):
    y = TITLE_H + 4 + i * (links_row_h + links_gap)
    links_rows.append((y,
                       shape.rounded_rectangle(14, y, screen.width - 28, links_row_h, 6),
                       shape.rounded_rectangle(14, y, screen.width - 28, links_row_h, 6).stroke(1.5)))

# layout of the QR page: the biggest whole-number scale that fits
qr_scale = max(1, 166 // qr_code.width)
qr_size = qr_code.width * qr_scale
qr_x = int(CX - qr_size / 2)
qr_y = TITLE_H + 8
qr_panel = shape.rounded_rectangle(qr_x - 4, qr_y - 4, qr_size + 8, qr_size + 8, 6)
qr_frame = shape.rounded_rectangle(qr_x - 6, qr_y - 6, qr_size + 12, qr_size + 12, 8).stroke(2)


def shadow_text(text, x, y, size, pen):
    screen.pen = SHADOW
    screen.text(text, x + 1, y + 2, font_size=size)
    screen.pen = pen
    screen.text(text, x, y, font_size=size)


def center_text(text, y, size, pen):
    w, _ = screen.measure_text(text, font_size=size)
    shadow_text(text, CX - (w / 2), y, size, pen)


def fit_size(text, size, max_width):
    # shrink long text until it fits the space available
    while size > 10:
        w, _ = screen.measure_text(text, font_size=size)
        if w <= max_width:
            break
        size -= 1
    return size


def pulse(speed, low, high):
    return low + (high - low) * ((math.sin(badge.ticks / speed) / 2) + 0.5)


def draw_page_dots():
    x = screen.width - 12 - (PAGE_COUNT - 1) * 9
    for i in range(PAGE_COUNT):
        screen.pen = ICE if i == page else color.rgb(120, 190, 255, 70)
        screen.shape(shape.circle(x + i * 9, 10, 3 if i == page else 2))


def draw_title(text):
    shadow_text(text, 14, 6, 20, STEEL)
    screen.pen = color.rgb(40, 120, 255, int(pulse(600, 120, 230)))
    screen.shape(shape.line(14, TITLE_H - 3, screen.width - 14, TITLE_H - 3, 1.5))


def draw_front():
    screen.blit(front_bg, vec2(0, 0))

    # name plate across the bottom, under the logo
    plate_y = 188
    screen.pen = PLATE
    screen.rectangle(0, plate_y, screen.width, screen.height - plate_y)
    screen.pen = color.rgb(40, 120, 255, int(pulse(600, 110, 255)))
    screen.shape(shape.line(0, plate_y, screen.width, plate_y, 2))

    center_text(id_name, plate_y + 3, fit_size(id_name, 30, screen.width - 20), STEEL)
    center_text(id_role, plate_y + 34, fit_size(id_role, 14, screen.width - 20), ICE)


def draw_links():
    screen.blit(dim_bg, vec2(0, 0))
    draw_title("Find me")

    pad = (links_row_h - links_icon) / 2
    text_x = 14 + pad + links_icon + 12
    for row, account in zip(links_rows, id_socials.items()):
        y, panel, outline = row
        name, details = account

        screen.pen = PANEL
        screen.shape(panel)
        screen.pen = color.rgb(40, 120, 255, 150)
        screen.shape(outline)

        icon = details["icon"]
        screen.blit(icon, rect(0, 0, icon.width, icon.height), rect(14 + pad, y + pad, links_icon, links_icon))

        handle = details["handle"]
        if links_row_h >= 38:
            size = fit_size(handle, 19, screen.width - 28 - text_x)
            shadow_text(handle, text_x, y + 3, size, STEEL)
            shadow_text(name, text_x, y + links_row_h - 17, 11, ICE)
        else:
            size = fit_size(handle, 15, screen.width - 28 - text_x)
            shadow_text(handle, text_x, y + (links_row_h - size) / 2 - 1, size, STEEL)


def draw_qr():
    screen.blit(dim_bg, vec2(0, 0))
    draw_title(qr_title)

    screen.pen = color.rgb(40, 120, 255, int(pulse(600, 120, 255)))
    screen.shape(qr_frame)
    screen.pen = color.rgb(255, 255, 255)
    screen.shape(qr_panel)
    screen.blit(qr_code, rect(0, 0, qr_code.width, qr_code.height), rect(qr_x, qr_y, qr_size, qr_size))

    caption = qr_url.split("://")[-1]
    caption_y = qr_y + qr_size + 8
    center_text(caption, caption_y, fit_size(caption, 15, screen.width - 20), ICE)


def init():
    pass


def update():
    global page

    # A and C step back and forth through the pages, B cycles like the old flip
    if badge.pressed(BUTTON_A):
        page = (page - 1) % PAGE_COUNT

    if badge.pressed(BUTTON_C) or badge.pressed(BUTTON_B):
        page = (page + 1) % PAGE_COUNT

    if page == PAGE_FRONT:
        draw_front()
    elif page == PAGE_LINKS:
        draw_links()
    else:
        draw_qr()

    draw_page_dots()


def on_exit():
    pass


run(update)
