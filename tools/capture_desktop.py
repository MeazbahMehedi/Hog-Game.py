"""Capture actual v3.1.0 Tk windows. Optional capture dependency: Pillow.

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


def capture(root, name):
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
    root.lift()
    root.after(180, root.quit)
    root.mainloop()
    root.update()
    root.winfo_pointerxy()
    x, y = root.winfo_rootx(), root.winfo_rooty()
    path = ROOT / 'docs/screenshots' / f'v{VERSION}-{name}.png'
    ImageGrab.grab(bbox=(x, y, x + root.winfo_width(), y + root.winfo_height())).save(path)
    print(path.name)


def seed_examples(app):
    alice = app.store.create_profile('Meazbah')
    bob = app.store.create_profile('Alex')
    for seed in (42, 43, 44):
        config = MatchConfig(2, ('Meazbah', 'Alex'), ('always5', 'always6'), seed, (alice, bob))
        session = GameSession(dice=seeded_dice(seed))
        events = []
        while not session.finished:
            who = session.current_player
            events.append(session.advance(STRATEGIES[config.strategies[who]][0](*session.scores[::1 if who == 0 else -1])))
        app.store.record_match(f'capture-{seed}', config, session, events)


def main():
    scenes = ('home', 'dashboard', 'compact-dashboard', 'game', 'compact-game', 'light', 'contrast', 'setup')
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
            if scene != 'home':
                seed_examples(app)
                app.show_home()
            if scene in ('game', 'compact-game', 'contrast'):
                app.start_match(MatchConfig(2, ('Meazbah', 'Alex'), ('always5', 'always6'), 42))
                for _ in range(10):
                    who = app.session.current_player
                    count = STRATEGIES[app.config.strategies[who]][0](*app.session.scores[::1 if who == 0 else -1])
                    app.complete_turn(count)
                    app.cancel_pending()
                app.select_count(6)
                if scene == 'contrast':
                    app.set_theme('contrast')
            elif scene == 'light':
                app.set_theme('light')
            elif scene == 'setup':
                app.show_setup(1)
                app.profile_vars[0].set('Meazbah')
                app._profile_selected(0)
                app.seed_var.set('42')
            if scene.startswith('compact'):
                root.geometry('960x720+20+20')
            capture(root, scene)
            if errors:
                raise errors[0]
        finally:
            app.close()


if __name__ == '__main__':
    main()
