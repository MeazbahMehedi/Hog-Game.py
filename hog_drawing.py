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


def draw_die(canvas, x, y, size, value, *, accent=False, palette=None, angle=0, skin="classic"):
    """Vector dice; rotation is cosmetic and never changes a game outcome."""
    palette = palette or PALETTES["dark"]
    fill = ("#f4c375" if palette is PALETTES["dark"] else "#ffdc9e") if accent else palette.die
    pip = palette.pip
    skins = {"cobalt": "#1d4ed8", "ruby": "#be123c", "nebula": "#6d28d9"}
    if skin in skins and not accent:
        fill, pip = skins[skin], "#ffffff"
    if accent:
        pip = "#172a32"
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
                           fill=pip, outline="")



def draw_avatar(canvas, name, size, palette, player=0, style="initials"):
    from hog_dashboard import initials
    canvas.delete("all")
    color = palette.accent if player == 0 else palette.gold
    canvas.create_oval(1, 1, size - 1, size - 1, fill=palette.raised, outline=color, width=2)
    if style == "panda":
        for x in (.25, .75):
            canvas.create_oval(size * (x - .12), size * .12, size * (x + .12), size * .36, fill="#15151a", outline="")
        canvas.create_oval(size * .18, size * .2, size * .82, size * .83, fill="#ffffff", outline="#15151a")
        for x in (.36, .64):
            canvas.create_oval(size * (x - .08), size * .4, size * (x + .08), size * .6, fill="#15151a", outline="")
            canvas.create_oval(size * (x - .02), size * .43, size * (x + .02), size * .48, fill="#ffffff", outline="")
        canvas.create_oval(size * .44, size * .63, size * .56, size * .71, fill="#15151a", outline="")
    elif style == "crown":
        points = ((.2,.7),(.15,.3),(.36,.48),(.5,.21),(.64,.48),(.85,.3),(.8,.7))
        canvas.create_polygon(*[coordinate * size for point in points for coordinate in point], fill=color, outline="")
        canvas.create_line(size * .22, size * .77, size * .78, size * .77, fill=color, width=2)
    else:
        canvas.create_text(size / 2, size / 2, text=initials(name), fill=color, font=("DejaVu Sans", max(10, int(size * .29)), "bold"))
