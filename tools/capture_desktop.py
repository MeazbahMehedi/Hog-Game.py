"""Capture actual v3.4.0 Tk windows. Optional capture dependency: Pillow.

Run on a graphical desktop: python tools/capture_desktop.py
All example data is held in memory; nothing is added to the user's database.
"""

from pathlib import Path
import sys
import subprocess
import json
from uuid import uuid4
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hog import GameSession, STRATEGIES, VERSION, seeded_dice
from hog_desktop import HogApp, tk
from hog_match import MatchConfig
from hog_preferences import Preferences
from hog_campaign import stages


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


CERTIFICATES = json.loads((ROOT / 'tests/fixtures/campaign_three_stars.json').read_text())


def seed_examples(app, identifier, completed=2):
    for stage in stages()[:completed]:
        choices = iter(CERTIFICATES[stage.identifier])
        session = GameSession(dice=seeded_dice(stage.seed))
        events = []
        while not session.finished:
            count = next(choices) if session.current_player == 0 else STRATEGIES[stage.strategy][0](session.scores[1], session.scores[0])
            events.append(session.advance(count))
        app.store.record_campaign(uuid4().hex, identifier, stage.identifier, events)


def drive_campaign(app, turns=None):
    choices = iter(CERTIFICATES[app.campaign_stage.identifier])
    while not app.campaign_session.finished and (turns is None or len(app.campaign_events) < turns):
        if app.analysis_pending is not None:
            app.root.after_cancel(app.analysis_pending)
            app.analysis_pending = None
        if app.campaign_session.current_player == 0:
            app.campaign_count_buttons[next(choices)].invoke()
            app.campaign_roll_button.invoke()
        else:
            app.campaign_cpu()
    if app.analysis_pending is not None:
        app.root.after_cancel(app.analysis_pending)
        app.analysis_pending = None


def main():
    scenes = ('dashboard', 'campaign-map', 'campaign-stage', 'campaign-cleared', 'wardrobe', 'milestones', 'aurora', 'cosmetic-game', 'empty-campaign')
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
            if scene == 'empty-campaign':
                app.show_campaign()
            else:
                identifier = app.store.create_profile('Meazbah')
                other = app.store.create_profile('Alex')
                completed = 6 if scene in ('wardrobe', 'milestones', 'cosmetic-game', 'aurora') else 0 if scene == 'campaign-cleared' else 2
                seed_examples(app, identifier, completed)
                app.show_home()
                if scene in ('campaign-map', 'wardrobe', 'milestones', 'aurora'):
                    app.show_campaign(identifier)
                    if scene == 'wardrobe':
                        app.store.equip_cosmetic(identifier, 'dice', 'nebula')
                        app.store.equip_cosmetic(identifier, 'avatar', 'panda')
                        app.store.equip_cosmetic(identifier, 'theme', 'twilight')
                        app.set_theme('twilight')
                        app.show_campaign(identifier)
                        page = app.campaign_tabs['Wardrobe'];page.master.select(page)
                    elif scene == 'milestones':
                        page = app.campaign_tabs['Milestones'];page.master.select(page)
                    elif scene == 'aurora':
                        app.store.equip_cosmetic(identifier, 'theme', 'aurora')
                        app.set_theme('aurora')
                elif scene == 'campaign-stage':
                    app.start_campaign_stage(identifier, 'the-pursuit')
                    drive_campaign(app, 6)
                elif scene == 'campaign-cleared':
                    app.start_campaign_stage(identifier, 'first-steps')
                    drive_campaign(app)
                elif scene == 'cosmetic-game':
                    app.store.equip_cosmetic(identifier, 'dice', 'nebula')
                    app.store.equip_cosmetic(identifier, 'avatar', 'panda')
                    app.set_theme('twilight')
                    app.start_match(MatchConfig(2, ('Meazbah', 'Alex'), seed=42, profile_ids=(identifier, other)))
                    for _ in range(9):
                        app.complete_turn(6)
                        app.cancel_pending()
            capture(root, scene, app.analysis_window)
            if errors:
                raise errors[0]
        finally:
            app.close()


if __name__ == '__main__':
    main()
