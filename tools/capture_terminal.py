"""Render actual subprocess output as readable terminal captures.

Optional documentation tool only: install Pillow to regenerate PNGs.
No game output is invented. Full raw transcripts are saved alongside images.
"""

import argparse
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "screenshots"


def capture(arguments, text="", cwd=ROOT):
    completed = subprocess.run([sys.executable, *arguments], input=text,
                               cwd=cwd, capture_output=True, text=True,
                               check=True, timeout=60)
    return completed.stdout


def font_path():
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                 "C:/Windows/Fonts/consola.ttf",
                 "/System/Library/Fonts/Menlo.ttc"):
        if Path(path).exists():
            return path
    raise SystemExit("Set up a monospace font (DejaVu Sans Mono, Consolas, or Menlo).")


def render(name, title, transcript, excerpt=None):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / f"{name}.txt").write_text(transcript, encoding="utf-8")
    lines = (excerpt if excerpt is not None else transcript).strip("\n").splitlines()
    font = ImageFont.truetype(font_path(), 18)
    small = ImageFont.truetype(font_path(), 14)
    line_height = 28
    width = max(1020, int(max(font.getlength(line) for line in lines)) + 80)
    height = 112 + len(lines) * line_height + 46
    canvas = Image.new("RGB", (width, height), "#0d1422")
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle((16, 16, width - 16, height - 16), radius=16,
                           fill="#121e30", outline="#2a3b54", width=2)
    draw.rounded_rectangle((17, 17, width - 17, 70), radius=15, fill="#1b2b42")
    for index, color in enumerate(("#ff6b75", "#ffc664", "#60d8a0")):
        left = 37 + index * 23
        draw.ellipse((left, 36, left + 11, 47), fill=color)
    draw.text((126, 30), title, font=small, fill="#e5eefb")
    for index, line in enumerate(lines):
        color = "#cbd8ea"
        if "H O G /" in line or "HOG /" in line:
            color = "#8fbaff"
        elif "SUS FUSS ->" in line or "wins!" in line:
            color = "#70e6b2"
        elif "SOW SAD ->" in line:
            color = "#ffc979"
        elif line.strip().startswith("[1]") or "STRATEGY COMPARISON" in line:
            color = "#a3c7ff"
        draw.text((38, 93 + index * line_height), line, font=font, fill=color)
    draw.text((38, height - 40), "Captured program output / styled terminal rendering",
              font=small, fill="#8b9ebc")
    canvas.save(OUTPUT / f"{name}.png")
    print(OUTPUT / f"{name}.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--legacy-dir", type=Path,
                        help="optional folder containing the original v1.0.0 modules")
    args = parser.parse_args()

    menu = capture(["hog_ui.py"], text="0\n")
    render("v1.1.0-menu", "Hog v1.1.0 / Main menu", menu)

    command = ["hog_ui.py", "-n", "0", "--strategy0", "adaptive", "--strategy1", "sus",
               "--name0", "Meazbah", "--name1", "Computer", "--seed", "42", "--no-replay"]
    game = capture(command)
    start = game.index("  TURN 11")
    end = game.index("  TURN 14")
    render("v1.1.0-game", "Hog v1.1.0 / Scoring detail (turns 11-13)", game,
           excerpt=game[start:end])
    start = game.rfind("\n============================================================================",
                       0, game.index("  H O G / MATCH COMPLETE"))
    render("v1.1.0-summary", "Hog v1.1.0 / Match summary", game, excerpt=game[start:])

    experiment = capture(["hog.py", "-r", "--games", "100", "--samples", "500", "--seed", "42"])
    render("v1.1.0-experiments", "Hog v1.1.0 / Strategy lab", experiment)

    if args.legacy_dir:
        old = capture(["-c", "import random; random.seed(42); "
                       "from hog_ui import play_with; play_with(0)"],
                      cwd=args.legacy_dir.resolve())
        render("v1.0.0-legacy", "Hog v1.0.0 / Original terminal output", old,
               excerpt="\n".join(old.splitlines()[:18]))


if __name__ == "__main__":
    main()
