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
from hog_preferences import Preferences


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
    path = ROOT / "docs" / "screenshots" / f"v3.0.0-{name}.png"
    ImageGrab.grab(bbox=box).save(path)
    print(path.name)


def main():
    # Each scene gets a fresh real window, avoiding stale backing pixels on
    # window-manager-free virtual displays. All match scores come from play.
    for scene in ("home", "setup", "game", "free-points", "winner", "rules", "light", "settings", "paused", "advisor", "comparison", "hub", "history", "leaderboard", "tournament", "resume", "profile-setup", "tutorial", "practice", "accessibility", "replay"):
        root = tk.Tk()
        errors = []
        root.report_callback_exception = lambda kind, error, traceback: errors.append(error)
        app = HogApp(root, cpu_delay=600000, preferences=Preferences(animations=False))
        root.geometry("1160x820+20+20")
        try:
            if scene in ("hub", "history", "leaderboard", "profile-setup", "replay"):
                identifier = app.store.create_profile("Meazbah")
                for seed in (42, 43, 44):
                    config = MatchConfig(1, ("Meazbah", "Computer"), ("adaptive", "hard"), seed, (identifier, None))
                    app.start_match(config)
                    while not app.session.finished:
                        app.cancel_pending()
                        who = app.session.current_player
                        count = STRATEGIES[config.strategies[who]][0](app.session.scores[who], app.session.scores[1 - who])
                        app.complete_turn(count)
                    app.cancel_pending()
                if scene == "replay":
                    app.show_replay()
                    app.replay_advance(8)
                elif scene == "profile-setup":
                    app.show_setup(1)
                    app.profile_vars[0].set("Meazbah")
                    app._profile_selected(0)
                else:
                    app.show_player_hub()
                    if scene in ("history", "leaderboard"):
                        page = app.hub_tabs["Match history" if scene == "history" else "Leaderboard"]
                        page.master.select(page)
            elif scene == "tutorial":
                app.show_tutorial()
                app.tutorial_answer_buttons[0].invoke()
                app.tutorial_next_button.invoke()
            elif scene == "practice":
                app.show_practice()
                app.practice_start_button.invoke()
                app.practice_play_button.invoke()
                if app.analysis_pending is not None:
                    root.after_cancel(app.analysis_pending)
                    app.analysis_pending = None
            elif scene == "accessibility":
                app.show_accessibility()
                app.set_theme("contrast")
            elif scene == "tournament":
                app.show_tournament()
                app.tournament_run_button.invoke()
            elif scene == "resume":
                app.start_match(MatchConfig(seed=42))
                app.select_count(0)
                app.roll_human()
                app.cancel_pending()
                app.computer_turn()
                app.save_current()
                app.resume_saved()
            elif scene == "advisor":
                app.start_match(MatchConfig(seed=42))
                app.show_advice()
            elif scene == "comparison":
                app.show_comparison()
                app.comparison_run_button.invoke()
            elif scene == "light":
                app.set_theme("light")
            elif scene == "settings":
                app.show_settings()
            elif scene == "paused":
                app.start_match(MatchConfig(seed=42))
                app.toggle_pause()
            elif scene == "setup":
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
            if scene in ("advisor", "comparison", "tournament"):
                def wait_ready():
                    text = app.analysis_status.cget("text")
                    if text.startswith(("Calculating", "Simulating", "Running")):
                        root.after(30, wait_ready)
                    else:
                        root.quit()
                root.after(30, wait_ready)
                root.mainloop()
            capture(root, scene, app.analysis_window if scene in ("advisor", "comparison", "hub", "history", "leaderboard", "tournament", "tutorial", "practice", "accessibility", "replay") else  app.rules_window if scene == "rules" else app.settings_window if scene == "settings" else None)
            if errors:
                raise errors[0]
        finally:
            app.close()


if __name__ == "__main__":
    main()
