"""Capture actual v4 Tk screens using temporary demonstration data. Needs Pillow."""

from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hog import GameSession, seeded_dice, STRATEGIES
from hog_backup import export_backup
from hog_campaign import stages
from hog_desktop import HogApp, tk
from hog_match import MatchConfig
from hog_preferences import Preferences
from capture_multiplayer import capture

SCENES = ('dashboard', 'welcome', 'welcome-rules', 'controls', 'profiles', 'backup', 'settings', 'game', 'compact', 'contrast')


def populate(app):
    player = app.store.create_profile('Meazbah')
    other = app.store.create_profile('Alex')
    config = MatchConfig(2, ('Meazbah', 'Alex'), seed=42, profile_ids=(player, other))
    session = GameSession(dice=seeded_dice(42)); events = []
    while not session.finished: events.append(session.advance(5))
    app.store.record_match(uuid4().hex, config, session, events)
    choices = json.loads((ROOT/'tests/fixtures/campaign_three_stars.json').read_text())
    for stage in stages()[:2]:
        session = GameSession(dice=seeded_dice(stage.seed)); events = []; human = iter(choices[stage.identifier])
        while not session.finished:
            count = next(human) if session.current_player == 0 else STRATEGIES[stage.strategy][0](session.scores[1], session.scores[0])
            events.append(session.advance(count))
        app.store.record_campaign(uuid4().hex, player, stage.identifier, events)
    app.store.equip_cosmetic(player, 'dice', 'cobalt')
    app.store.archive_profile(other)
    return config


def main():
    if len(sys.argv) == 1:
        for scene in SCENES: subprocess.run([sys.executable, __file__, scene], check=True)
        return
    for scene in sys.argv[1:]:
        if scene not in SCENES: raise ValueError('Unknown capture scene')
        with tempfile.TemporaryDirectory() as directory:
            root = tk.Tk(); errors = []
            root.report_callback_exception = lambda kind, error, trace: errors.append(error)
            app = HogApp(root, preferences=Preferences(animations=False, welcome_seen=True))
            root.geometry('1280x880+20+20'); root.update()
            config = populate(app)
            try:
                app.show_home(); target = None
                if scene.startswith('welcome'):
                    app.show_welcome()
                    if scene == 'welcome-rules': app.welcome_next_button.invoke()
                    target = app.analysis_window
                elif scene == 'controls':
                    app.show_controls(); app.control_vars[0].set('z'); app.controls_apply_button.invoke()
                    target = app.analysis_window
                elif scene == 'profiles':
                    app.show_profile_manager(); target = app.analysis_window
                elif scene == 'backup':
                    file = Path(directory)/'demo.hogbackup'
                    export_backup(file, app.store, app.preferences)
                    app.show_data_center(); app.preview_portable_backup(file)
                    deadline = time.monotonic()+30
                    while app.backup_future is not None and time.monotonic() < deadline:
                        root.update(); time.sleep(.01)
                    if app.backup_candidate is None: raise RuntimeError(app.backup_status.cget('text'))
                    target = app.analysis_window
                elif scene == 'settings':
                    app.show_settings(); target = app.settings_window
                elif scene == 'game':
                    app.preferences = replace(app.preferences, shortcuts=('z', *app.preferences.shortcuts[1:]))
                    app.start_match(config)
                    for count in (5, 0, 4, 6): app.complete_turn(count)
                elif scene == 'compact': root.geometry('960x720+20+20')
                elif scene == 'contrast':
                    app.set_theme('contrast'); app.show_controls(); target = app.analysis_window
                root.update()
                capture(root, scene, target)
                if errors: raise errors[0]
            finally:
                app.close()


if __name__ == '__main__': main()
