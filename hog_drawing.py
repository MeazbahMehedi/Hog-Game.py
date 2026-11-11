"""Vector dice shared by live play and recorded replays."""

import math
from hog_preferences import PALETTES

PIPS = {
    1: ((1, 1),),
    2: ((0, 0), (2, 2)),
    3: ((0, 0), (1, 1), (2, 2)),
    4: ((0, 0), (2, 0), (0, 2), (2, 2)),
    5: ((0, 0), (2, 0), (1, 1), (0, 2), (2, 2)),
    6: ((0, 0), (0, 1), (0, 2), (2, 0), (2, 1), (2, 2)),
}


def draw_die(canvas, x, y, size, value, *, accent=False, palette=None, angle=0):
    """Vector dice; rotation is cosmetic and never changes a game outcome."""
    palette = palette or PALETTES["dark"]
    fill = ("#f4c375" if palette is PALETTES["dark"] else "#ffdc9e") if accent else palette.die
    radians = math.radians(angle)
    center_x, center_y = x + size / 2, y + size / 2

    def rotate(px, py):
        dx, dy = px - center_x, py - center_y
        return (center_x + dx * math.cos(radians) - dy * math.sin(radians),
                center_y + dx * math.sin(radians) + dy * math.cos(radians))

    corners = [rotate(x, y), rotate(x + size, y),
               rotate(x + size, y + size), rotate(x, y + size)]
    shadow = [(px + 3, py + 4) for px, py in corners]
    canvas.create_polygon(shadow, fill=palette.shadow, outline="")
    canvas.create_polygon(corners, fill=fill, outline=palette.border, width=1)
    radius = size * .062
    for column, row in PIPS[value]:
        cx, cy = rotate(x + size * (.26 + column * .24), y + size * (.26 + row * .24))
        canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                           fill=palette.pip, outline="")

