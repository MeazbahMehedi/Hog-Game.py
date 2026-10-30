"""Capture actual Tk windows for documentation. Optional dependency: Pillow.

Run on a graphical desktop: python tools/capture_desktop.py
Linux CI: xvfb-run -a python tools/capture_desktop.py
"""

from pathlib import Path
import sys

from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hog import STRATEGIES
from hog_desktop import HogApp, tk
from hog_match import MatchConfig


def capture(root, name, window=None):
    root.update()
    target = window if window is not None else root
    target.lift()
    root.after(150, root.quit)
    root.mainloop()
    root.update()
    # A server query synchronizes Tk's drawing before the separate grab client.
    target.winfo_pointerxy()
    x, y = target.winfo_rootx(), target.winfo_rooty()
    box = (x, y, x + target.winfo_width(), y + target.winfo_height())
    path = ROOT / "docs" / "screenshots" / f"v1.2.0-{name}.png"
    ImageGrab.grab(bbox=box).save(path)
    print(path.name)


def main():
    # Each scene gets a fresh real window, avoiding stale backing pixels on
    # window-manager-free virtual displays. All match scores come from play.
    for scene in ("home", "setup", "game", "free-points", "winner", "rules"):
        root = tk.Tk()
        errors = []
        root.report_callback_exception = lambda kind, error, traceback: errors.append(error)
        app = HogApp(root, cpu_delay=600000)
        root.geometry("1160x820+20+20")
        try:
            if scene == "setup":
                app.show_setup(1)
                app.name_vars[0].set("Meazbah")
                app.seed_var.set("42")
            elif scene in ("game", "free-points", "winner"):
                app.start_match(MatchConfig(1, ("Meazbah", "Computer"), ("adaptive", "sus"), 42))
                target_turns = {"game": 10, "free-points": 11, "winner": float("inf")}[scene]
                while not app.session.finished and len(app.events) < target_turns:
                    app.cancel_pending()
                    who = app.session.current_player
                    if app.config.is_human(who):
                        strategy = STRATEGIES[app.config.strategies[who]][0]
                        app.select_count(strategy(app.session.scores[who], app.session.scores[1 - who]))
                        app.roll_human()
                    else:
                        app.computer_turn()
                    app.cancel_pending()
                if scene == "winner":
                    app.show_winner()
            elif scene == "rules":
                app.show_rules()
            capture(root, scene, app.rules_window if scene == "rules" else None)
            if errors:
                raise errors[0]
        finally:
            app.close()


if __name__ == "__main__":
    main()
