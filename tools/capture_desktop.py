"""Capture actual v3.3.0 Tk windows. Optional capture dependency: Pillow.

Run on a graphical desktop: python tools/capture_desktop.py
All example data is held in memory; nothing is added to the user's database.
"""

from pathlib import Path
import sys
import subprocess
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hog import GameSession, STRATEGIES, VERSION, seeded_dice
from hog_desktop import HogApp, tk
from hog_match import MatchConfig
from hog_preferences import Preferences


def capture(root, name, target=None):
    # Force a fresh mapping before capture on window-manager-free displays.
    root.withdraw()
    root.update()
    root.deiconify()
    root.update()
    def expose(widget):
        widget.event_generate("<Expose>")
        for child in widget.winfo_children():
            expose(child)
    expose(root)
    root.update()
    (target or root).deiconify()
    (target or root).lift()
    expose(target or root)
    root.update()
    root.after(180, root.quit)
    root.mainloop()
    root.update()
    target = target or root
    target.winfo_pointerxy()
    x, y = target.winfo_rootx(), target.winfo_rooty()
    path = ROOT / 'docs/screenshots' / f'v{VERSION}-{name}.png'
    ImageGrab.grab(bbox=(x, y, x + target.winfo_width(), y + target.winfo_height())).save(path)
    print(path.name)


def seed_examples(app):
    own = app.store.create_profile('Meazbah')
    other = app.store.create_profile('Alex')
    for seed in range(42, 54):
        opponent = ('always5', 'always6', 'catch-up', 'medium')[seed % 4]
        config = MatchConfig(1, ('Meazbah', opponent), ('adaptive', opponent), seed, (own, None))
        session = GameSession(dice=seeded_dice(seed))
        events = []
        while not session.finished:
            who = session.current_player
            count = (session.turn_number * 3 + seed) % 11 if who == 0 else STRATEGIES[opponent][0](session.scores[1], session.scores[0])
            events.append(session.advance(count))
        app.store.record_match(f'capture-{seed}', config, session, events)
    return own


def main():
    scenes = ('dashboard', 'coach-hub', 'live-coach', 'coach-explanation', 'review', 'review-explanation', 'puzzles', 'puzzle-solved', 'puzzle-contrast')
    if len(sys.argv) == 1:
        for scene in scenes:
            subprocess.run([sys.executable, __file__, scene], check=True)
        return
    for scene in sys.argv[1:]:
        if scene not in scenes:
            raise ValueError('Unknown capture scene')
        root = tk.Tk()
        errors = []
        root.report_callback_exception = lambda kind, error, trace: errors.append(error)
        app = HogApp(root, cpu_delay=600000, preferences=Preferences(animations=False))
        root.geometry('1280x880+20+20')
        root.update()
        try:
            seed_examples(app)
            app.show_home()
            if scene == 'coach-hub':
                app.show_coaching_hub()
            elif scene in ('live-coach', 'coach-explanation'):
                app.start_match(MatchConfig(2, ('Meazbah', 'Alex'), seed=42))
                for _ in range(8):
                    app.complete_turn((app.session.turn_number * 3) % 11)
                app.select_count(7)
                app.show_coach()
            elif scene in ('review', 'review-explanation'):
                app.show_review()
            elif scene.startswith('puzzle'):
                app.show_puzzles()
                if scene == 'puzzle-contrast':
                    app.set_theme('contrast')
            if scene not in ('dashboard', 'coach-hub'):
                def ready():
                    if app.analysis_pending is None:
                        root.quit()
                    else:
                        root.after(15, ready)
                root.after(15, ready)
                timeout = root.after(10000, root.quit)
                root.mainloop()
                root.after_cancel(timeout)
                if app.analysis_pending is not None:
                    raise RuntimeError('Analysis timed out during capture')
            if scene in ('coach-explanation', 'review-explanation'):
                # Select the actual explanation notebook tab.
                def select_explanation(widget):
                    if widget.winfo_class() == 'TNotebook':
                        widget.select(1)
                        return True
                    return any(select_explanation(child) for child in widget.winfo_children())
                select_explanation(app.analysis_window)
            if scene in ('puzzle-solved', 'puzzle-contrast'):
                app.puzzle_buttons[app.puzzle_report.recommended].invoke()
                app.puzzle_submit.invoke()
            capture(root, scene, app.analysis_window)
            if errors:
                raise errors[0]
        finally:
            app.close()


if __name__ == '__main__':
    main()
