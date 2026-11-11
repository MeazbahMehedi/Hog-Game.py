"""Dependency-free Canvas charts for recorded dice choices and score progress."""

import math


def draw_dice_choices(canvas, counts, palette, family):
    canvas.delete('all')
    width, height = max(canvas.winfo_width(), 300), max(canvas.winfo_height(), 160)
    left, right, top, bottom = 42, width - 20, 30, height - 38
    maximum = max(max(counts), 1)
    canvas.create_text(left, 12, text='RECORDED DICE CHOICES / number of turns', anchor='w',
                       fill=palette.muted, font=(family, 9, 'bold'))
    for fraction in (0, .5, 1):
        y = bottom - (bottom - top) * fraction
        canvas.create_line(left, y, right, y, fill=palette.border)
        canvas.create_text(left - 8, y, text=f'{maximum * fraction:g}', anchor='e', fill=palette.muted, font=(family, 9))
    step = (right - left) / 11
    for index, count in enumerate(counts):
        x = left + step * (index + .5)
        end = bottom - (bottom - top) * count / maximum
        if count:
            canvas.create_rectangle(x - step * .28, end, x + step * .28, bottom,
                                    fill=palette.gold if index == 0 else palette.accent, outline='')
            canvas.create_text(x, end - 8, text=str(count), fill=palette.text, font=(family, 9))
        canvas.create_text(x, bottom + 16, text=str(index), fill=palette.text, font=(family, 9))
    if not sum(counts):
        canvas.create_text((left + right) / 2, (top + bottom) / 2, text='Complete a match to see dice choices.',
                           fill=palette.muted, font=(family, 11))


def score_position(canvas, total, x):
    """Map a click to the nearest recorded turn, including the initial state."""
    span = max(1, canvas.winfo_width() - 66)
    return max(0, min(total, round((x - 46) / span * total)))


def draw_scores(canvas, states, names, palette, family, position=0, moments=()):
    canvas.delete('all')
    if not states:
        return
    width, height = max(canvas.winfo_width(), 300), max(canvas.winfo_height(), 160)
    left, right, top, bottom = 46, width - 20, 32, height - 32
    total = len(states) - 1
    maximum = max(100, math.ceil(max(max(state['scores']) for state in states) / 25) * 25)

    def point(index, score):
        return left + (right - left) * index / max(total, 1), bottom - (bottom - top) * score / maximum

    for value in range(0, maximum + 1, 25):
        y = point(0, value)[1]
        canvas.create_line(left, y, right, y, fill=palette.border, dash=(4, 4) if value == 100 else ())
        canvas.create_text(left - 8, y, text=str(value), anchor='e', fill=palette.muted, font=(family, 8))
    for index in sorted({0, total // 2, total}):
        x = point(index, 0)[0]
        canvas.create_text(x, bottom + 16, text=f'T{index}', fill=palette.muted, font=(family, 8))
    for seat, color in ((0, palette.accent), (1, palette.gold)):
        label = names[seat] if len(names[seat]) <= 18 else names[seat][:17] + '…'
        canvas.create_text(left + seat * 220, 12, text=f'● {label}', anchor='w', fill=color, font=(family, 10, 'bold'))
        points = [coordinate for index, state in enumerate(states) for coordinate in point(index, state['scores'][seat])]
        if len(points) >= 4:
            canvas.create_line(*points, fill=color, width=2)
    for number, _title in moments:
        x = point(number, 0)[0]
        canvas.create_oval(x - 2, bottom - 2, x + 2, bottom + 2, fill=palette.text, outline='')
    position = max(0, min(total, position))
    x = point(position, 0)[0]
    canvas.create_line(x, top, x, bottom, fill=palette.text, dash=(3, 4))
    for seat, color in ((0, palette.accent), (1, palette.gold)):
        px, py = point(position, states[position]['scores'][seat])
        canvas.create_oval(px - 4, py - 4, px + 4, py + 4, fill=color, outline=palette.panel)
