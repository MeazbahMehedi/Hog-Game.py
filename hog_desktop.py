"""The Game of Hog - Graphical Desktop Edition.

Run: python hog_desktop.py. Tkinter is the only UI dependency.
Canvas dice are drawn with vector shapes; no image assets are needed at runtime.
"""

import argparse
import sys
from dataclasses import fields, replace
import math
import json
import sqlite3
from uuid import uuid4
from pathlib import Path
from random import Random
from concurrent.futures import ThreadPoolExecutor
from hog_ai import policy, analyze_moves, advice_text, compare_opponents

try:
    import tkinter as tk
    from tkinter import font as tkfont, messagebox, ttk, filedialog
except ImportError:
    tk = None

from hog import GOAL, STRATEGIES, VERSION, GameSession, seeded_dice, sus_update
from hog_match import MatchConfig
from hog_storage import Store
from hog_tournament import run_tournament, export_tournament
from hog_showcase import PracticeRules, tutorial_lessons, replay_states
from hog_dashboard import initials, turn_breakdown, recent_results
from hog_insights_ui import InsightsUI
from hog_coach_ui import CoachUI
from hog_campaign_ui import CampaignUI
from hog_drawing import draw_die, draw_avatar
from hog_audio import SoundPlayer
from hog_preferences import (PALETTES, BASE_THEMES, PACE_DELAYS, Preferences, default_preferences_path,
                             load_preferences, save_preferences)



class HogApp(CampaignUI, CoachUI, InsightsUI):
    """Event-driven desktop views. Computer turns use cancellable Tk timers."""

    def __init__(self, root, *, cpu_delay=None, preferences=None, preferences_path=None, data_path=None):
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="hog-analysis")
        self.policy_future = self.worker.submit(policy)
        self.analysis_window = None
        self._redraw_insights = None
        self.analysis_pending = None
        self.storage_error = ""
        try:
            self.store = Store(data_path)
        except (OSError, sqlite3.Error):
            self.store = Store()
            self.storage_error = "Persistent data could not be opened. This session uses temporary storage."
        self.match_id = None
        self.root = root
        self.preferences_path = Path(preferences_path) if preferences_path is not None else None
        self.preferences = preferences or (load_preferences(self.preferences_path)
                                           if self.preferences_path is not None else Preferences())
        self.palette = PALETTES[self.preferences.theme]
        self.cpu_delay = PACE_DELAYS[self.preferences.pace] if cpu_delay is None else cpu_delay
        self.audio = SoundPlayer(enabled=self.preferences.sound)
        self.paused = False
        self.animating = False
        self._visual_rng = Random(4817)
        self._visual_outcomes = ()
        self._animation_frame = 0
        self._roll_count = 0
        self.settings_window = None
        self._settings_resume = False
        self.settings_save_error = ""
        self.pending = None
        self.ui_pending = None
        self.layout_pending = None
        self.journal_mode = None
        self.journal_visible = False
        self._pulse_phase = False
        self.session = None
        self.config = None
        self.events = []
        self.screen = "home"
        self.rules_window = None
        root.title(f"Hog | Campaign Edition v{VERSION}")
        height = max(720, min(880, root.winfo_screenheight() - 70))
        root.geometry(f"1280x{height}")
        root.minsize(960, 720)
        root.configure(bg=self.palette.bg)
        root.protocol("WM_DELETE_WINDOW", self.close)
        families = tkfont.families(root)
        self.family = next((family for family in ("Segoe UI", "DejaVu Sans", "Helvetica")
                            if family in families), "TkDefaultFont")
        root.option_add("*Font", (self.family, 10))
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Hog.TCombobox", fieldbackground=self.palette.bg, background=self.palette.raised,
                        foreground=self.palette.text, arrowcolor=self.palette.accent, padding=8)
        style.map("Hog.TCombobox", fieldbackground=[("readonly", self.palette.bg)],
                  foreground=[("readonly", self.palette.text), ("disabled", self.palette.muted)])
        root.option_add("*TCombobox*Listbox.background", self.palette.panel)
        root.option_add("*TCombobox*Listbox.foreground", self.palette.text)
        self.shell = tk.Frame(root, bg=self.palette.bg)
        self.shell.pack(fill="both", expand=True, padx=22, pady=18)
        top = tk.Frame(self.shell, bg=self.palette.bg)
        top.pack(fill="x", pady=(0, 14))
        self.label(top, "HOG", 26, bold=True, fg=self.palette.accent).pack(side="left")
        self.label(top, "  /  THE DICE GAME", 9, fg=self.palette.muted).pack(side="left", pady=(7, 0))
        self.button(top, "Rules", self.show_rules, kind="secondary").pack(side="right")
        self.button(top, "Dashboard", self.navigate_home, kind="secondary").pack(side="right", padx=8)
        self.button(top, "Settings", self.show_settings, kind="secondary").pack(side="right", padx=(0, 8))
        self.button(top, "Access", self.show_accessibility, kind="secondary").pack(side="right", padx=(0, 8))
        self.theme_button = self.button(top, "Light mode" if self.preferences.theme == "dark" else "Dark mode",
                                        self.toggle_theme, kind="secondary")
        self.theme_button.pack(side="right", padx=(0, 8))
        self.label(top, f"v{VERSION}", 9, fg=self.palette.muted).pack(side="right", padx=14)
        self.body = tk.Frame(self.shell, bg=self.palette.bg)
        self.body.pack(fill="both", expand=True)
        footer = tk.Frame(self.shell, bg=self.palette.bg)
        footer.pack(fill="x", pady=(14, 0))
        self.label(footer, "LOCAL PLAY   /   2 PLAYERS   /   FIRST TO 100", 8, fg=self.palette.muted).pack(side="left")
        self.label(footer, "A little luck. A better decision.", 9, fg=self.palette.accent).pack(side="right")
        root.bind("<KeyPress>", self._keyboard)
        root.bind("<Configure>", self._queue_layout, add="+")
        root.bind("<MouseWheel>", self._dashboard_wheel, add="+")
        root.bind("<Button-4>", self._dashboard_wheel, add="+")
        root.bind("<Button-5>", self._dashboard_wheel, add="+")
        self.show_home()

    def label(self, parent, text, size=11, *, bold=False, fg=None, bg=None, **kwargs):
        display_size = size + 2 if self.preferences.large_text and size <= 13 else size
        label = tk.Label(parent, text=text, font=(self.family, display_size, "bold" if bold else "normal"),
                         bg=bg or parent.cget("bg"), fg=fg or self.palette.text, anchor="w", justify="left", **kwargs)
        label._hog_base_font = (self.family, size, "bold" if bold else "normal")
        return label

    def button(self, parent, text, command, *, kind="primary", **kwargs):
        fill, foreground = (self.palette.accent, self.palette.accent_text) if kind == "primary" else (self.palette.raised, self.palette.text)
        button = tk.Button(parent, text=text, command=command,
                         bg=fill, fg=foreground, activebackground=self.palette.gold,
                         activeforeground=self.palette.accent_text, disabledforeground=self.palette.disabled,
                         font=(self.family, 10, "bold"), relief="flat", bd=0,
                         padx=18, pady=10, cursor="hand2", highlightthickness=2,
                         highlightbackground=fill, highlightcolor=self.palette.gold, **kwargs)
        button._hog_base_font = (self.family, 10, "bold")
        if self.preferences.large_text:
            button.configure(font=(self.family, 12, "bold"))
        button._hog_kind = kind
        return button

    def panel(self, parent, **kwargs):
        return tk.Frame(parent, bg=self.palette.panel, highlightbackground=self.palette.border,
                        highlightthickness=1, **kwargs)

    def clear(self, screen):
        self.cancel_pending()
        self._cancel_ui()
        self.animating = False
        self.paused = False
        self._visual_outcomes = ()
        self.screen = screen
        if self.preferences.large_text:
            self.root.after_idle(self._resize_text)
        for child in self.body.winfo_children():
            child.destroy()

    def cancel_pending(self):
        if self.pending is not None:
            self.root.after_cancel(self.pending)
            self.pending = None

    def close(self):
        self.cancel_pending()
        self._cancel_ui()
        if self.layout_pending is not None:
            self.root.after_cancel(self.layout_pending)
            self.layout_pending = None
        self.audio.stop()
        self.close_analysis()
        self.worker.shutdown(wait=False, cancel_futures=True)
        self.store.close()
        self.root.destroy()

    def navigate_home(self):
        if self.session and not self.session.finished and self.screen == "game":
            if not self.confirm_change("Leave match?", "Return home and leave this unfinished match?"):
                return
        self.session = None
        self.show_home()

    def confirm_change(self, title, text):
        was_paused = self.paused
        if not was_paused:
            self.toggle_pause()
        accepted = messagebox.askyesno(title, text, parent=self.root)
        if not accepted and not was_paused:
            self.toggle_pause()
        return accepted

    def restart_match(self):
        if self.screen != "game" or self.config is None:
            return
        if not self.session.finished and not self.confirm_change(
                "Restart match?", "Restart from zero with the same players, strategies and seed?"):
            return
        self.start_match(self.config)

    def toggle_pause(self):
        if self.screen != "game" or self.session.finished:
            return
        self.paused = not self.paused
        if self.paused:
            self.cancel_pending()
            self.audio.stop()
        self.refresh_game()
        if not self.paused and self.animating:
            if self.preferences.animations:
                self.schedule_animation()
            else:
                self.finish_roll()

    def _persist_preferences(self):
        self.settings_save_error = ""
        if self.preferences_path is not None:
            try:
                save_preferences(self.preferences_path, self.preferences)
            except OSError:
                self.settings_save_error = "Applied for this session; the settings file could not be saved."
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_status.configure(text=self.settings_save_error or "Changes apply immediately.")

    def set_theme(self, theme):
        if theme == self.preferences.theme:
            return
        updated = replace(self.preferences, theme=theme)
        old, new = self.palette, PALETTES[updated.theme]
        self.preferences, self.palette = updated, new
        # Button text can share a color with a surface; buttons are styled below.
        colors = {getattr(old, field.name): getattr(new, field.name)
                  for field in fields(old) if field.name != "accent_text"}

        def recolor(widget):
            options = widget.keys()
            for key in ("background", "foreground", "activebackground", "activeforeground",
                        "highlightbackground", "highlightcolor", "insertbackground",
                        "selectbackground", "selectforeground", "disabledforeground", "selectcolor", "troughcolor"):
                if key in options:
                    value = str(widget.cget(key)).lower()
                    if value in colors:
                        widget.configure(**{key: colors[value]})
            if isinstance(widget, tk.Button) and hasattr(widget, "_hog_kind"):
                primary = widget._hog_kind == "primary"
                fill = new.accent if primary else new.raised
                widget.configure(bg=fill, fg=new.accent_text if primary else new.text,
                                 activeforeground=new.accent_text,
                                 disabledforeground=new.disabled, highlightbackground=fill)
            if isinstance(widget, tk.Canvas):
                for item in widget.find_all():
                    for key in ("fill", "outline"):
                        try:
                            value = widget.itemcget(item, key).lower()
                            if value in colors:
                                widget.itemconfigure(item, **{key: colors[value]})
                        except tk.TclError:
                            pass
            for child in widget.winfo_children():
                recolor(child)

        recolor(self.root)
        self.refresh_profile_art()
        style = ttk.Style(self.root)
        style.configure("Hog.TCombobox", fieldbackground=new.bg, background=new.raised,
                        foreground=new.text, arrowcolor=new.accent)
        style.map("Hog.TCombobox", fieldbackground=[("disabled", new.raised), ("readonly", new.bg)],
                  foreground=[("disabled", new.muted), ("readonly", new.text)])
        self.root.option_add("*TCombobox*Listbox.background", new.panel)
        self.root.option_add("*TCombobox*Listbox.foreground", new.text)
        self.theme_button.configure(text="Light mode" if theme == "dark" else "Dark mode")
        if self.screen == "game":
            self.journal.tag_configure("turn", foreground=new.accent)
            self.journal.tag_configure("rule", foreground=new.gold)
            self.refresh_game()
        if self._redraw_insights is not None:
            self._redraw_insights()
        self._sync_settings()
        self._persist_preferences()

    def toggle_theme(self):
        self.set_theme("light" if self.preferences.theme == "dark" else "dark")

    def set_animations(self, enabled):
        self.preferences = replace(self.preferences, animations=bool(enabled))
        if self.animating and not self.paused and not self.preferences.animations:
            self.cancel_pending()
            self.finish_roll()
        if self.screen == "game":
            self.refresh_game()
        self._sync_settings()
        self._persist_preferences()

    def set_sound(self, enabled):
        enabled = bool(enabled) and self.audio.available
        self.preferences = replace(self.preferences, sound=enabled)
        self.audio.enabled = enabled
        if not enabled:
            self.audio.stop()
        self._sync_settings()
        self._persist_preferences()

    def set_pace(self, pace):
        self.preferences = replace(self.preferences, pace=pace)
        self.cpu_delay = PACE_DELAYS[pace]
        if self.screen == "game" and not self.animating:
            self.cancel_pending()
            self.refresh_game()
        self._sync_settings()
        self._persist_preferences()

    def _sync_settings(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_theme.set(self.preferences.theme)
            self.settings_motion.set(self.preferences.animations)
            self.settings_sound.set(self.preferences.sound and self.audio.available)
            self.settings_pace.set(self.preferences.pace)

    def show_settings(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        self._settings_resume = bool(self.screen == "game" and not self.session.finished and not self.paused)
        if self._settings_resume:
            self.toggle_pause()
        window = tk.Toplevel(self.root)
        self.settings_window = window
        window.title("Hog / Settings & shortcuts")
        window.geometry("680x720")
        window.minsize(660, 690)
        window.configure(bg=self.palette.bg)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", self.close_settings)
        inner = tk.Frame(window, bg=self.palette.bg)
        inner.pack(fill="both", expand=True, padx=30, pady=24)
        self.label(inner, "MAKE IT YOUR TABLE", 9, fg=self.palette.accent).pack(anchor="w")
        self.label(inner, "Settings & shortcuts", 25, bold=True).pack(anchor="w", pady=(8, 18))
        self.label(inner, "Theme", 11, bold=True).pack(anchor="w", pady=(0, 7))
        self.settings_theme = tk.StringVar(self.root, self.preferences.theme)
        theme = ttk.Combobox(inner, textvariable=self.settings_theme, values=BASE_THEMES + (() if self.preferences.theme in BASE_THEMES else (self.preferences.theme,)),
                             state="readonly", style="Hog.TCombobox")
        theme.pack(fill="x", pady=(0, 15))
        theme.bind("<<ComboboxSelected>>", lambda _event: self.set_theme(self.settings_theme.get()))
        self.settings_motion = tk.BooleanVar(self.root, self.preferences.animations)
        self.settings_sound = tk.BooleanVar(self.root, self.preferences.sound and self.audio.available)
        for title, variable, command in (
                ("Animate dice rolls", self.settings_motion, lambda: self.set_animations(self.settings_motion.get())),
                ("Enable sound effects", self.settings_sound, lambda: self.set_sound(self.settings_sound.get()))):
            check = tk.Checkbutton(inner, text=title, variable=variable, command=command,
                                    bg=self.palette.bg, fg=self.palette.text,
                                    activebackground=self.palette.bg, activeforeground=self.palette.accent,
                                    selectcolor=self.palette.raised, disabledforeground=self.palette.muted,
                                    anchor="w", padx=0, pady=6, cursor="hand2")
            check.pack(fill="x")
            if variable is self.settings_sound and not self.audio.available:
                check.configure(state="disabled")
        self.label(inner, "Turn animations off for reduced motion and immediate results.",
                   9, fg=self.palette.muted).pack(anchor="w", pady=(4, 5))
        self.label(inner, f"Audio: {self.audio.description}. Sound is optional.",
                   9, fg=self.palette.muted, wraplength=600).pack(anchor="w", pady=(0, 17))
        self.label(inner, "Computer pace", 11, bold=True).pack(anchor="w", pady=(0, 7))
        self.settings_pace = tk.StringVar(self.root, self.preferences.pace)
        pace = ttk.Combobox(inner, textvariable=self.settings_pace, values=tuple(PACE_DELAYS),
                            state="readonly", style="Hog.TCombobox")
        pace.pack(fill="x", pady=(0, 20))
        pace.bind("<<ComboboxSelected>>", lambda _event: self.set_pace(self.settings_pace.get()))
        self.label(inner, "KEYBOARD CONTROLS", 9, bold=True, fg=self.palette.accent).pack(anchor="w")
        self.label(inner, "0-9 / choose dice     X / choose 10     Enter / roll\n"
                          "P / pause or resume   R / restart       Esc / home\n"
                          "T / switch theme      M / mute          F1 / rules", 10,
                   fg=self.palette.muted).pack(anchor="w", pady=(8, 15))
        self.settings_status = self.label(inner, self.settings_save_error or "Changes apply immediately.",
                                          9, fg=self.palette.muted, wraplength=600)
        self.settings_status.pack(anchor="w", pady=(0, 14))
        self.button(inner, "Done", self.close_settings).pack(anchor="w")

    def close_settings(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.destroy()
        self.settings_window = None
        should_resume = self._settings_resume
        self._settings_resume = False
        if should_resume and self.screen == "game" and self.paused:
            self.toggle_pause()

    def _keyboard(self, event):
        key = event.keysym.lower()
        if key == "f1":
            self.show_rules()
            return "break"
        # Entry editing and journal text selection retain normal keyboard behavior.
        if event.widget.winfo_class() in ("Entry", "TEntry", "TCombobox", "Text", "Spinbox"):
            return None
        if event.state & 0x000C:  # Control or Alt: keep platform shortcuts intact.
            return None
        if key == "t":
            self.toggle_theme()
        elif key == "m":
            self.set_sound(not self.preferences.sound)
        elif key == "escape":
            self.navigate_home()
        elif self.screen == "game":
            if key in "0123456789" and len(key) == 1:
                self.select_count(int(key))
            elif key == "x":
                self.select_count(10)
            elif key == "return":
                self.roll_human()
            elif key == "p":
                self.toggle_pause()
            elif key == "r":
                self.restart_match()
            elif key == "h":
                self.show_advice()
            else:
                return None
        else:
            return None
        return "break"

    def avatar(self, parent, name, player=0, size=42, *, profile_id=None):
        canvas = tk.Canvas(parent, width=size, height=size, bg=parent.cget("bg"), highlightthickness=0)
        canvas._hog_avatar = (name, player, size, profile_id)
        draw_avatar(canvas, name, size, self.palette, player, self.profile_equipment(profile_id)['avatar'])
        return canvas

    def _queue_layout(self, event=None):
        if event is not None and event.widget is not self.root:
            return
        if self.layout_pending is None:
            self.layout_pending = self.root.after_idle(self._apply_layout)

    def _apply_layout(self):
        self.layout_pending = None
        width = self.root.winfo_width()
        if self.screen == "home":
            compact = width < 1180
            if compact != getattr(self, "dashboard_compact", None):
                self.dashboard_compact = compact
                self.dashboard_nav.grid_forget()
                self.dashboard_view.grid_forget()
                self.dashboard_nav_title.grid_remove()
                self.dashboard_nav_note.grid_remove()
                for button in self.dashboard_buttons:
                    button.grid_forget()
                if compact:
                    self.dashboard_nav.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
                    for column, button in enumerate(self.dashboard_buttons):
                        button.grid(row=column // 6, column=column % 6, sticky="ew", padx=2, pady=3)
                    self.dashboard_view.grid(row=1, column=0, columnspan=2, sticky="nsew")
                    self.dashboard_frame.rowconfigure(0, weight=0)
                    self.dashboard_frame.rowconfigure(1, weight=1)
                    self.dashboard_frame.columnconfigure(0, weight=0)
                    self.dashboard_art.pack_forget()
                else:
                    self.dashboard_nav.grid(row=0, column=0, sticky="ns", padx=(0, 18))
                    self.dashboard_nav_title.grid(row=0, column=0, sticky="w", padx=12, pady=(18, 14))
                    for row, button in enumerate(self.dashboard_buttons, 1):
                        button.grid(row=row, column=0, sticky="ew", padx=8, pady=4)
                    self.dashboard_nav_note.grid(row=len(self.dashboard_buttons) + 2, column=0, sticky="sw", padx=12, pady=18)
                    self.dashboard_view.grid(row=0, column=1, sticky="nsew")
                    self.dashboard_frame.rowconfigure(0, weight=1)
                    self.dashboard_frame.rowconfigure(1, weight=0)
                    self.dashboard_art.pack(side="right", padx=18, pady=12)
            self.dashboard_scroll.configure(scrollregion=self.dashboard_scroll.bbox("all"))
        elif self.screen == "game":
            visible = width >= 1180 if self.journal_mode is None else self.journal_mode
            if visible != self.journal_visible:
                self.journal_visible = visible
                if visible:
                    self.journal_panel.grid(row=0, column=1, sticky="nsew", padx=(16, 0))
                else:
                    self.journal_panel.grid_remove()
            self.journal_button.configure(text="Hide journal" if visible else "Show journal")

    def _dashboard_wheel(self, event):
        if self.screen != "home":
            return
        # Only the dashboard itself scrolls; floating rules/settings keep their own input.
        if event.widget.winfo_toplevel() is not self.root:
            return
        if self.dashboard_scroll.bbox("all")[3] <= self.dashboard_scroll.winfo_height():
            return
        step = -1 if getattr(event, "num", None) == 4 else 1 if getattr(event, "num", None) == 5 else -int(event.delta / 120)
        self.dashboard_scroll.yview_scroll(step, "units")

    def _cancel_ui(self):
        if self.ui_pending is not None:
            self.root.after_cancel(self.ui_pending)
            self.ui_pending = None

    def _pulse_turn(self):
        self.ui_pending = None
        if self.screen != "game" or self.paused or self.session.finished or not self.preferences.animations:
            return
        self._pulse_phase = not self._pulse_phase
        who = self.session.current_player
        self.active_labels[who].configure(fg=self.palette.gold if self._pulse_phase else self.palette.accent)
        self.ui_pending = self.root.after(650, self._pulse_turn)

    def toggle_journal(self):
        if self.screen == "game":
            self.journal_mode = not self.journal_visible
            self._apply_layout()

    def show_home(self):
        self.clear("home")
        self.dashboard_compact = None
        frame = self.dashboard_frame = tk.Frame(self.body, bg=self.palette.bg)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)
        nav = self.dashboard_nav = self.panel(frame)
        self.dashboard_nav_title = self.label(nav, "YOUR TABLE", 9, bold=True, fg=self.palette.muted)
        self.dashboard_nav_note = self.label(nav, "OFFLINE PLAY\nNo account needed", 9, fg=self.palette.muted)
        navigation = (("Dashboard", self.show_home), ("Play", lambda: self.show_setup(1)),
                      ("Learn", self.show_tutorial), ("Practice", self.show_practice),
                      ("Players", self.show_player_hub), ("Replay", self.show_replay),
                      ("Tournaments", self.show_tournament), ("Compare", self.show_comparison),
                      ("Stats", self.show_statistics), ("Coach", self.show_coaching_hub),
                      ("Campaign", self.show_campaign))
        self.dashboard_buttons = []
        for title, command in navigation:
            button = self.button(nav, title, command, kind="primary" if title == "Dashboard" else "secondary")
            button.configure(padx=10, pady=6)
            self.dashboard_buttons.append(button)
        view = self.dashboard_view = tk.Frame(frame, bg=self.palette.bg)
        scroll = self.dashboard_scroll = tk.Canvas(view, bg=self.palette.bg, highlightthickness=0)
        scrollbar = tk.Scrollbar(view, command=scroll.yview)
        scrollbar.pack(side="right", fill="y")
        scroll.pack(side="left", fill="both", expand=True)
        scroll.configure(yscrollcommand=scrollbar.set, yscrollincrement=28)
        content = tk.Frame(scroll, bg=self.palette.bg)
        window = scroll.create_window(0, 0, window=content, anchor="nw")
        scroll.bind("<Configure>", lambda event: scroll.itemconfigure(window, width=event.width))
        content.bind("<Configure>", lambda _event: scroll.configure(scrollregion=scroll.bbox("all")))
        heading = tk.Frame(content, bg=self.palette.bg)
        heading.pack(fill="x", pady=(0, 12))
        self.label(heading, "Your next great decision.", 24, bold=True).pack(side="left")
        self.label(heading, "DASHBOARD / LOCAL", 8, fg=self.palette.muted).pack(side="right", pady=(8, 0))
        hero = self.panel(content)
        hero.pack(fill="x", pady=(0, 12))
        copy = tk.Frame(hero, bg=self.palette.panel)
        copy.pack(side="left", fill="both", expand=True, padx=22, pady=18)
        self.label(copy, "ROLL WITH A PLAN", 9, fg=self.palette.accent, bold=True).pack(anchor="w")
        self.label(copy, "A little luck. A better decision.", 23, bold=True).pack(anchor="w", pady=(7, 6))
        self.label(copy, "Race to 100. Learn the rules. Find your winning move.", 10,
                   fg=self.palette.muted).pack(anchor="w")
        actions = tk.Frame(copy, bg=self.palette.panel)
        actions.pack(anchor="w", pady=(14, 0))
        self.button(actions, "Start a match  >", lambda: self.show_setup(1)).pack(side="left")
        self.button(actions, "Resume saved", self.resume_saved, kind="secondary").pack(side="left", padx=10)
        art = self.dashboard_art = tk.Canvas(hero, width=190, height=155, bg=self.palette.panel, highlightthickness=0)
        art.create_oval(4, 0, 183, 154, fill=self.palette.hero, outline="")
        draw_die(art, 22, 22, 73, 5, palette=self.palette, angle=-9)
        draw_die(art, 99, 72, 62, 3, palette=self.palette, angle=9)
        history, profiles = self.store.history(), self.store.stats()
        self.dashboard_counts = (len(history), len(profiles), len(self.store.tournaments()))
        metrics = tk.Frame(content, bg=self.palette.bg)
        metrics.pack(fill="x", pady=(0, 12))
        for column, (title, count) in enumerate(zip(("COMPLETED MATCHES", "LOCAL PROFILES", "SAVED TOURNAMENTS"), self.dashboard_counts)):
            metrics.columnconfigure(column, weight=1, uniform="metrics")
            card = self.panel(metrics)
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 5, 0 if column == 2 else 5))
            self.label(card, title, 8, fg=self.palette.muted).pack(anchor="w", padx=16, pady=(10, 3))
            self.label(card, str(count), 22, bold=True).pack(anchor="w", padx=16, pady=(0, 9))
        self.label(content, "CHOOSE YOUR TABLE", 9, bold=True, fg=self.palette.muted).pack(anchor="w", pady=(0, 8))
        modes = tk.Frame(content, bg=self.palette.bg)
        modes.pack(fill="x", pady=(0, 12))
        self.dashboard_mode_buttons = []
        for column, (mode, title, note) in enumerate(((1, "You vs computer", "Nine strategies to challenge."),
                                                     (2, "Pass & play", "Two people. One screen."),
                                                     (0, "Strategy showdown", "Watch two computers compete."))):
            modes.columnconfigure(column, weight=1, uniform="modes")
            card = self.panel(modes)
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 5, 0 if column == 2 else 5))
            self.label(card, f"0{column + 1} / " + ("SOLO", "LOCAL", "WATCH")[column], 8, fg=self.palette.gold).pack(anchor="w", padx=16, pady=(12, 7))
            self.label(card, title, 15, bold=True).pack(anchor="w", padx=16)
            self.label(card, note, 9, fg=self.palette.muted).pack(anchor="w", padx=16, pady=(5, 10))
            button = self.button(card, "Choose mode  >", lambda chosen=mode: self.show_setup(chosen), kind="secondary")
            button.configure(pady=6, padx=12)
            button.pack(anchor="w", padx=16, pady=(0, 12))
            self.dashboard_mode_buttons.append(button)
        bottom = tk.Frame(content, bg=self.palette.bg)
        bottom.pack(fill="x")
        for col in (0, 1):
            bottom.columnconfigure(col, weight=1, uniform="bottom")
        players = self.panel(bottom)
        players.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self.label(players, "PLAYERS AT YOUR TABLE", 9, bold=True, fg=self.palette.muted).pack(anchor="w", padx=16, pady=(12, 8))
        if not profiles:
            self.label(players, "Make the table yours.", 13, bold=True).pack(anchor="w", padx=16)
            self.label(players, "Create a profile to track wins and milestones.", 9, fg=self.palette.muted).pack(anchor="w", padx=16, pady=(4, 8))
        for index, profile in enumerate(profiles[:2]):
            row = tk.Frame(players, bg=self.palette.panel)
            row.pack(fill="x", padx=16, pady=4)
            self.avatar(row, profile["name"], index, 34, profile_id=profile["id"]).pack(side="left", padx=(0, 10))
            self.label(row, profile["name"], 11, bold=True).pack(side="left")
            self.label(row, f'{profile["wins"]} wins / {profile["played"]} played', 9, fg=self.palette.muted).pack(side="right")
        self.button(players, "Manage players", self.show_player_hub, kind="secondary").pack(anchor="w", padx=16, pady=(4, 12))
        recent = self.panel(bottom)
        recent.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self.label(recent, "RECENT MATCHES", 9, bold=True, fg=self.palette.muted).pack(anchor="w", padx=16, pady=(12, 8))
        results = recent_results(history)
        if not results:
            self.label(recent, "Your story starts with a match.", 13, bold=True).pack(anchor="w", padx=16)
            self.label(recent, "Completed desktop matches appear here.", 9, fg=self.palette.muted).pack(anchor="w", padx=16, pady=(4, 8))
        for title, score in results:
            row = tk.Frame(recent, bg=self.palette.panel)
            row.pack(fill="x", padx=16, pady=8)
            self.label(row, title, 10, wraplength=245).pack(side="left")
            self.label(row, score, 12, bold=True, fg=self.palette.accent).pack(side="right")
        self.button(recent, "Open replays", self.show_replay, kind="secondary").pack(anchor="w", padx=16, pady=(4, 12))
        if self.storage_error:
            self.label(content, self.storage_error, 9, fg=self.palette.red, wraplength=700).pack(anchor="w", pady=10)
        self._queue_layout()

    def show_setup(self, mode=1):
        self.clear("setup")
        self.label(self.body, "MATCH SETUP", 9, fg=self.palette.accent).pack(anchor="w")
        self.label(self.body, "Set your table.", 30, bold=True).pack(anchor="w", pady=(6, 5))
        self.label(self.body, "Name your players and choose who makes the decisions.", 11, fg=self.palette.muted).pack(anchor="w", pady=(0, 20))
        self.mode_var = tk.IntVar(self.root, value=mode)
        mode_row = tk.Frame(self.body, bg=self.palette.bg)
        mode_row.pack(fill="x", pady=(0, 22))
        for count, title in ((1, "You vs computer"), (2, "Two human players"), (0, "Computer vs computer")):
            tk.Radiobutton(mode_row, text=title, variable=self.mode_var, value=count,
                           command=self._setup_mode_changed, bg=self.palette.bg, fg=self.palette.text,
                           selectcolor=self.palette.raised, activebackground=self.palette.bg, activeforeground=self.palette.accent,
                           padx=14, pady=8, cursor="hand2").pack(side="left", padx=(0, 18))
        cards = tk.Frame(self.body, bg=self.palette.bg)
        cards.pack(fill="x")
        self.name_vars = []
        self.strategy_vars = []
        self.strategy_boxes = []
        self.control_labels = []
        self.strategy_hints = []
        self.profile_vars = []
        self.profile_boxes = []
        self.profile_lookup = {"Guest / no profile": None}
        for profile in self.store.profiles():
            self.profile_lookup[profile["name"]] = profile["id"]
        initial_names = ("Player 0", "Player 1" if mode == 2 else "Computer")
        if mode == 0:
            initial_names = ("Computer 0", "Computer 1")
        titles = [f"{key} / {value[1]}" for key, value in STRATEGIES.items()]
        for player in (0, 1):
            cards.columnconfigure(player, weight=1, uniform="players")
            card = self.panel(cards)
            card.grid(row=0, column=player, sticky="nsew", padx=(0, 10) if player == 0 else (10, 0))
            inner = tk.Frame(card, bg=self.palette.panel)
            inner.pack(fill="both", expand=True, padx=25, pady=14)
            self.label(inner, f"PLAYER {player}", 9, fg=self.palette.accent if player == 0 else self.palette.gold).pack(anchor="w")
            control = self.label(inner, "", 16, bold=True)
            control.pack(anchor="w", pady=(7, 18))
            self.control_labels.append(control)
            self.label(inner, "Local profile", 9, fg=self.palette.muted).pack(anchor="w")
            profile_var = tk.StringVar(self.root, "Guest / no profile")
            self.profile_vars.append(profile_var)
            profile_box = ttk.Combobox(inner, textvariable=profile_var, values=tuple(self.profile_lookup),
                                       state="readonly", style="Hog.TCombobox")
            profile_box.pack(fill="x", pady=(4, 8))
            self.profile_boxes.append(profile_box)
            profile_box.bind("<<ComboboxSelected>>", lambda _event, seat=player: self._profile_selected(seat))
            self.label(inner, "Display name", 10, fg=self.palette.muted).pack(anchor="w", pady=(0, 6))
            name = tk.StringVar(self.root, initial_names[player])
            self.name_vars.append(name)
            entry = tk.Entry(inner, textvariable=name, bg=self.palette.bg, fg=self.palette.text, insertbackground=self.palette.accent,
                             relief="flat", highlightthickness=1, highlightbackground=self.palette.border,
                             highlightcolor=self.palette.accent, font=(self.family, 12))
            entry.pack(fill="x", ipady=10, pady=(0, 18))
            self.label(inner, "Computer strategy", 10, fg=self.palette.muted).pack(anchor="w", pady=(0, 6))
            selected = tk.StringVar(self.root, titles[0 if player == 0 else 5])
            self.strategy_vars.append(selected)
            combo = ttk.Combobox(inner, textvariable=selected, values=titles,
                                 state="readonly", style="Hog.TCombobox", font=(self.family, 10))
            combo.pack(fill="x")
            self.strategy_boxes.append(combo)
            hint = self.label(inner, "", 9, fg=self.palette.muted, wraplength=390, height=2)
            hint.pack(anchor="w", pady=(10, 0))
            self.strategy_hints.append(hint)
            combo.bind("<<ComboboxSelected>>", lambda _event: self._setup_mode_changed())
        bottom = tk.Frame(self.body, bg=self.palette.bg)
        bottom.pack(fill="x", pady=(24, 0))
        self.label(bottom, "Optional random seed", 10, fg=self.palette.muted).pack(side="left")
        self.seed_var = tk.StringVar(self.root)
        tk.Entry(bottom, textvariable=self.seed_var, width=15, bg=self.palette.panel, fg=self.palette.text,
                 insertbackground=self.palette.accent, relief="flat").pack(side="left", padx=14, ipady=9)
        self.label(bottom, "Leave blank for a new dice sequence.", 9, fg=self.palette.muted).pack(side="left")
        self.button(bottom, "Begin match  >", self._begin_from_setup).pack(side="right")
        self.setup_error = self.label(self.body, "", 10, fg=self.palette.red, wraplength=1000)
        self.setup_error.pack(anchor="w", pady=(14, 0))
        self._setup_mode_changed()

    def _setup_mode_changed(self):
        mode = self.mode_var.get()
        for player in (0, 1):
            human = mode == 2 or (mode == 1 and player == 0)
            self.control_labels[player].configure(text="Human player" if human else "Computer player")
            self.strategy_boxes[player].configure(state="disabled" if human else "readonly")
            self.profile_boxes[player].configure(state="readonly" if human else "disabled")
            if not human:
                self.profile_vars[player].set("Guest / no profile")
            key = self.strategy_vars[player].get().split(" / ")[0]
            hint = "You choose the dice on each turn." if human else STRATEGIES[key][2]
            self.strategy_hints[player].configure(text=hint)

    def _begin_from_setup(self):
        try:
            seed = self.seed_var.get().strip()
            config = MatchConfig(self.mode_var.get(),
                                 tuple(name.get().strip() for name in self.name_vars),
                                 tuple(strategy.get().split(" / ")[0] for strategy in self.strategy_vars),
                                 int(seed) if seed else None,
                                 tuple(self.profile_lookup[var.get()] for var in self.profile_vars))
        except (ValueError, KeyError):
            self.setup_error.configure(text="Use names of 1-20 printable characters and a whole-number seed (or leave it blank).")
            return
        self.start_match(config)

    def start_match(self, config):
        self.cancel_pending()
        self.audio.stop()
        self.config = config
        self.match_id = uuid4().hex
        self.session = GameSession(dice=seeded_dice(config.seed))
        self.events = []
        self.selected_count = 5
        self.journal_mode = None
        self.build_game()

    def build_game(self):
        self.clear("game")
        title = tk.Frame(self.body, bg=self.palette.bg)
        title.pack(fill="x", pady=(0, 12))
        self.label(title, "MATCH TABLE", 9, bold=True, fg=self.palette.accent).pack(side="left")
        self.turn_label = self.label(title, "", 11, fg=self.palette.muted)
        self.turn_label.pack(side="left", padx=12)
        self.journal_button = self.button(title, "Show journal", self.toggle_journal, kind="secondary")
        self.journal_button.configure(pady=5, padx=8, font=(self.family, 9, "bold"))
        self.journal_button.pack(side="right", padx=(6, 0))
        self.save_button = self.button(title, "Save", self.save_current, kind="secondary")
        self.save_button.configure(pady=5, padx=10, font=(self.family, 9, "bold"))
        self.save_button.pack(side="right", padx=4)
        self.restart_button = self.button(title, "Restart / R", self.restart_match, kind="secondary")
        self.restart_button.configure(pady=5, padx=10, font=(self.family, 9, "bold"))
        self.restart_button.pack(side="right")
        self.advice_button = self.button(title, "Coach / H", self.show_advice, kind="secondary")
        self.advice_button.configure(pady=5, padx=10, font=(self.family, 9, "bold"))
        self.advice_button.pack(side="right", padx=(0, 8))
        self.pause_button = self.button(title, "Pause / P", self.toggle_pause, kind="secondary")
        self.pause_button.configure(pady=5, padx=10, font=(self.family, 9, "bold"))
        self.pause_button.pack(side="right", padx=8)
        scores = tk.Frame(self.body, bg=self.palette.bg)
        scores.pack(fill="x", pady=(0, 12))
        self.score_panels, self.score_labels, self.score_bars, self.active_labels = [], [], [], []
        for player in (0, 1):
            scores.columnconfigure(player, weight=1, uniform="scores")
            card = self.panel(scores)
            card.grid(row=0, column=player, sticky="nsew", padx=(0, 9) if player == 0 else (9, 0))
            self.score_panels.append(card)
            inside = tk.Frame(card, bg=self.palette.panel)
            inside.pack(fill="x", padx=22, pady=14)
            top = tk.Frame(inside, bg=self.palette.panel)
            top.pack(fill="x")
            self.avatar(top, self.config.names[player], player, 36, profile_id=self.config.profile_ids[player]).pack(side="left", padx=(0, 10))
            self.label(top, self.config.names[player], 15, bold=True).pack(side="left")
            active = self.label(top, "", 9, fg=self.palette.accent)
            active.pack(side="right")
            self.active_labels.append(active)
            score_row = tk.Frame(inside, bg=self.palette.panel)
            score_row.pack(fill="x", pady=(4, 3))
            score = self.label(score_row, "0", 38, bold=True)
            score.pack(side="left")
            self.label(score_row, " / 100", 13, fg=self.palette.muted).pack(side="left", pady=(15, 0))
            control = "HUMAN" if self.config.is_human(player) else self.config.strategies[player].upper()
            self.label(score_row, control.replace("ALWAYS", "ALWAYS "), 9, fg=self.palette.muted).pack(side="right", pady=(15, 0))
            self.score_labels.append(score)
            bar = tk.Canvas(inside, height=5, bg=self.palette.raised, highlightthickness=0)
            bar.pack(fill="x")
            bar.bind("<Configure>", lambda _event: self._redraw_bars())
            self.score_bars.append(bar)
        table = self.match_table = tk.Frame(self.body, bg=self.palette.bg)
        table.pack(fill="both", expand=True)
        table.columnconfigure(0, weight=1)
        table.rowconfigure(0, weight=1)
        left = self.panel(table)
        left.grid(row=0, column=0, sticky="nsew")
        inner = tk.Frame(left, bg=self.palette.panel)
        inner.pack(fill="both", expand=True, padx=18, pady=12)
        self.label(inner, "ON THE TABLE", 9, fg=self.palette.muted, bold=True).pack(anchor="w")
        self.dice_canvas = tk.Canvas(inner, bg=self.palette.panel, height=105, highlightthickness=0)
        self.dice_canvas.pack(fill="x", pady=(2, 0))
        self.dice_canvas.bind("<Configure>", lambda _event: self._draw_outcomes())
        self.result_label = self.label(inner, "", 11, bold=True, wraplength=650)
        self.result_label.pack(anchor="w", fill="x", pady=(0, 5))
        breakdown = tk.Frame(inner, bg=self.palette.panel)
        breakdown.pack(fill="x", pady=(0, 4))
        self.breakdown_labels = []
        for column in range(3):
            breakdown.columnconfigure(column, weight=1, uniform="breakdown")
            cell = tk.Frame(breakdown, bg=self.palette.raised)
            cell.grid(row=0, column=column, sticky="ew", padx=(0 if column == 0 else 3, 0 if column == 2 else 3))
            caption = self.label(cell, "", 8, fg=self.palette.muted)
            caption.pack(anchor="w", padx=10, pady=(5, 0))
            value = self.label(cell, "", 17, bold=True, fg=self.palette.accent if column == 1 else self.palette.text)
            value.pack(anchor="w", padx=10, pady=(0, 5))
            self.breakdown_labels.extend((caption, value))
        self.bonus_label = self.label(inner, "", 9, fg=self.palette.accent, wraplength=650)
        self.bonus_label.pack(anchor="w", fill="x")
        self.label(inner, "CHOOSE YOUR DICE", 9, fg=self.palette.muted, bold=True).pack(anchor="w", pady=(9, 6))
        selector = tk.Frame(inner, bg=self.palette.panel)
        selector.pack(fill="x")
        self.count_buttons = []
        for count in range(11):
            selector.columnconfigure(count, weight=1, uniform="dice")
            button = self.button(selector, str(count), lambda choice=count: self.select_count(choice),
                                 kind="secondary", width=2)
            button.configure(padx=0, pady=7, font=(self.family, 10, "bold"))
            button.grid(row=0, column=count, padx=2, sticky="ew")
            self.count_buttons.append(button)
        self.free_label = self.label(inner, "", 9, fg=self.palette.muted, wraplength=610)
        self.free_label.pack(anchor="w", pady=(7, 7))
        action_row = tk.Frame(inner, bg=self.palette.panel)
        action_row.pack(fill="x")
        self.action_button = self.button(action_row, "", self.roll_human)
        self.action_button.pack(side="left")
        self.status_label = self.label(action_row, "", 9, fg=self.palette.muted, wraplength=280)
        self.status_label.pack(side="left", padx=15)
        right = self.journal_panel = self.panel(table, width=280)
        self.journal_visible = False
        right.pack_propagate(False)
        self.label(right, "MATCH JOURNAL", 9, fg=self.palette.muted, bold=True).pack(anchor="w", padx=18, pady=(18, 5))
        self.label(right, "The story so far", 15, bold=True).pack(anchor="w", padx=18, pady=(0, 14))
        history_container = tk.Frame(right, bg=self.palette.panel)
        history_container.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        scrollbar = tk.Scrollbar(history_container, relief="flat")
        scrollbar.pack(side="right", fill="y")
        self.journal = tk.Text(history_container, bg=self.palette.panel, fg=self.palette.text, font=(self.family, 10),
                               relief="flat", wrap="word", state="disabled", width=23,
                               yscrollcommand=scrollbar.set, padx=4, spacing3=6)
        self.journal.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=self.journal.yview)
        self.journal.tag_configure("turn", foreground=self.palette.accent, font=(self.family, 10, "bold"))
        self.journal.tag_configure("rule", foreground=self.palette.gold)
        self.refresh_game()
        self._apply_layout()

    def _redraw_bars(self):
        if self.screen != "game":
            return
        for player, canvas in enumerate(self.score_bars):
            canvas.delete("all")
            end = canvas.winfo_width() * min(self.session.scores[player] / GOAL, 1)
            canvas.create_rectangle(0, 0, end, 6, fill=self.palette.accent if player == 0 else self.palette.gold, outline="")

    def _draw_outcomes(self):
        if self.screen != "game":
            return
        canvas = self.dice_canvas
        canvas.delete("all")
        width = canvas.winfo_width()
        if self.animating:
            count = len(self._visual_outcomes)
            size = min(52, max(30, (width - 18) / max(1, count) - 10))
            spacing = size + 10
            start = max(0, (width - (count * spacing - 10)) / 2)
            for index, value in enumerate(self._visual_outcomes):
                phase = self._animation_frame * .8 + index
                draw_die(canvas, start + index * spacing, 20 + math.sin(phase) * 5,
                         size, value, palette=self.palette, angle=math.sin(phase) * 13, skin=self.seat_skin(self.session.current_player))
            text = "PAUSED / roll animation held" if self.paused else "ROLLING / preview faces only"
            canvas.create_text(width / 2, 94, text=text, fill=self.palette.muted,
                               font=(self.family, 9, "bold"))
            return
        if not self.events:
            canvas.create_text(width / 2, 48, text="Your next move starts here.",
                               fill=self.palette.muted, font=(self.family, 14))
            return
        event = self.events[-1]
        if not event.outcomes:
            canvas.create_text(width / 2, 47, text="0 DICE. GUARANTEED POINTS.",
                               fill=self.palette.accent, font=(self.family, 14, "bold"))
            canvas.create_text(width / 2, 82, text=f"Boar Brawl +{event.turn_points}",
                               fill=self.palette.text, font=(self.family, 18, "bold"))
            return
        count = len(event.outcomes)
        size = min(56, max(32, (width - 16) / count - 9))
        spacing = size + 9
        start = max(0, (width - (count * spacing - 9)) / 2)
        for index, value in enumerate(event.outcomes):
            draw_die(canvas, start + index * spacing, 18, size, value, accent=value == 1, palette=self.palette, skin=self.seat_skin(event.player))

    def select_count(self, count):
        if (self.screen == "game" and not self.paused and not self.animating
                and not self.session.finished and self.config.is_human(self.session.current_player)):
            self.selected_count = count
            self._refresh_controls()

    def _refresh_controls(self):
        finished = self.session.finished
        who = self.session.current_player
        human = not finished and not self.paused and not self.animating and self.config.is_human(who)
        for count, button in enumerate(self.count_buttons):
            selected = count == self.selected_count
            button.configure(state="normal" if human else "disabled", bg=self.palette.accent if selected else self.palette.raised,
                             fg=self.palette.accent_text if selected else self.palette.text, highlightbackground=self.palette.accent if selected else self.palette.raised)
        self.save_button.configure(state="disabled" if finished else "normal")
        self.advice_button.configure(state="normal" if human else "disabled")
        self.pause_button.configure(text="Resume / P" if self.paused else "Pause / P",
                                    state="disabled" if finished else "normal")
        if self.paused:
            self.free_label.configure(text="Match paused. Scores, dice and the journal will not advance.")
            self.action_button.configure(text="Paused", state="disabled")
            self.status_label.configure(text="Use Resume / P when you are ready.")
        elif self.animating:
            self.free_label.configure(text="Preview faces are cosmetic. The scoring roll is resolved once, at the end.")
            self.action_button.configure(text="Rolling...", state="disabled")
            self.status_label.configure(text="P pauses this animation.")
        elif finished:
            self.free_label.configure(text="This match is complete. Review the final turns in the journal.")
            self.action_button.configure(text="Match summary", state="normal", command=self.show_winner)
            self.status_label.configure(text="Final table")
        elif human:
            before = self.session.scores[who]
            gain = sus_update(0, before, self.session.scores[1 - who]) - before
            if self.selected_count == 0:
                preview = f"Selected: 0 dice / guaranteed +{gain}, including any Sus Fuss bonus."
            else:
                risk = (1 - (5 / 6) ** self.selected_count) * 100
                preview = f"Selected: {self.selected_count} dice / {risk:.0f}% Sow Sad risk. Zero dice: guaranteed +{gain}."
            self.free_label.configure(text=preview)
            text = "Take free points" if self.selected_count == 0 else f"Roll {self.selected_count} dice"
            self.action_button.configure(text=text, state="normal", command=self.roll_human)
            self.status_label.configure(text=f"{self.config.names[who]}'s turn / Enter to play")
        else:
            self.free_label.configure(text="The computer follows its selected strategy and uses the same fair dice.")
            self.action_button.configure(text="Computer's turn", state="disabled")
            self.status_label.configure(text=f"{self.config.names[who]} is choosing...")

    def refresh_game(self):
        who = self.session.current_player
        for player in (0, 1):
            active = not self.session.finished and who == player
            self.score_labels[player].configure(text=str(self.session.scores[player]))
            indicator = "YOUR TURN" if self.config.is_human(player) else "COMPUTER TURN"
            self.active_labels[player].configure(text=("PAUSED" if self.paused else indicator) if active else "WAITING" if not self.session.finished else "FINISHED",
                                                 fg=self.palette.accent if active else self.palette.muted)
            self.score_panels[player].configure(highlightbackground=self.palette.accent if active else self.palette.border,
                                                highlightthickness=2 if active else 1)
        prefix = "PAUSED / " if self.paused else "ROLLING / " if self.animating else ""
        self.turn_label.configure(text="MATCH COMPLETE" if self.session.finished else f"{prefix}TURN {self.session.turn_number:02d}")
        if self.events:
            event = self.events[-1]
            name = self.config.names[event.player]
            rule = "Boar Brawl" if event.num_rolls == 0 else "Sow Sad" if 1 in event.outcomes else "Dice total"
            self.result_label.configure(text=f"{name}: +{event.turn_points} points / {rule}")
            ordinary = event.score_before + event.turn_points
            text = (f"Sus Fuss: {ordinary} becomes {event.score_after} (+{event.bonus} bonus)"
                    if event.bonus else f"{event.score_before} + {event.turn_points} = {event.score_after}")
            self.bonus_label.configure(text=text)
        else:
            self.result_label.configure(text="Make your first move.")
            self.bonus_label.configure(text="Choose 0-10 dice. Any rolled 1 makes the turn worth 1 point.")
        for label, text in zip(self.breakdown_labels, turn_breakdown(self.events[-1] if self.events else None)):
            label.configure(text=text)
        self._draw_outcomes()
        self._redraw_bars()
        self._refresh_controls()
        self._cancel_ui()
        if not self.paused and not self.session.finished and self.preferences.animations:
            self.ui_pending = self.root.after(650, self._pulse_turn)
        self.journal.configure(state="normal")
        self.journal.delete("1.0", "end")
        if not self.events:
            self.journal.insert("end", "Match ready.\nPlayer 0 goes first.\n")
        for event in self.events:
            bonus = f" +{event.bonus} bonus" if event.bonus else ""
            self.journal.insert("end", f"{event.number:02d}  {self.config.names[event.player]}\n", "turn")
            rule = "Boar Brawl" if event.num_rolls == 0 else "Sow Sad" if 1 in event.outcomes else "Dice total"
            self.journal.insert("end", f"{rule} / {event.num_rolls} dice\n", "rule")
            self.journal.insert("end", f"+{event.turn_points}{bonus} / Total {event.score_after}\n\n")
        self.journal.configure(state="disabled")
        self.journal.see("end")
        if (not self.session.finished and not self.paused and not self.animating
                and not self.config.is_human(who) and self.pending is None):
            self.pending = self.root.after(self.cpu_delay, self.computer_turn)

    def _enter_roll(self, _event=None):
        if self.screen == "game":
            self.roll_human()

    def roll_human(self):
        if (self.screen != "game" or self.paused or self.animating or self.session.finished
                or not self.config.is_human(self.session.current_player)):
            return
        self.complete_turn(self.selected_count)

    def computer_turn(self):
        self.pending = None
        if (self.screen != "game" or self.paused or self.animating or self.session.finished
                or self.config.is_human(self.session.current_player)):
            return
        who = self.session.current_player
        if self.config.strategies[who] == "hard" and not self.policy_future.done():
            self.pending = self.root.after(30, self.computer_turn)
            return
        strategy = STRATEGIES[self.config.strategies[who]][0]
        count = strategy(self.session.scores[who], self.session.scores[1 - who])
        self.complete_turn(count)

    def complete_turn(self, count):
        if self.screen != "game" or self.paused or self.animating or self.session.finished:
            return
        self.cancel_pending()
        if self.preferences.animations and count > 0:
            self.animating = True
            self._roll_count = count
            self._animation_frame = 0
            self._visual_outcomes = tuple(self._visual_rng.randint(1, 6) for _ in range(count))
            self.audio.play("roll")
            self.refresh_game()
            self.schedule_animation()
        else:
            self.commit_turn(count)

    def schedule_animation(self):
        if self.screen == "game" and self.animating and not self.paused and self.pending is None:
            self.pending = self.root.after(45, self.animation_tick)

    def animation_tick(self):
        self.pending = None
        if self.screen != "game" or self.paused or not self.animating:
            return
        self._animation_frame += 1
        if self._animation_frame >= 12:
            self.finish_roll()
            return
        self._visual_outcomes = tuple(self._visual_rng.randint(1, 6) for _ in range(self._roll_count))
        self._draw_outcomes()
        self.schedule_animation()

    def finish_roll(self):
        if not self.animating or self.paused:
            return
        self.cancel_pending()
        count = self._roll_count
        self.animating = False
        self._visual_outcomes = ()
        self.commit_turn(count)

    def commit_turn(self, count):
        event = self.session.advance(count)
        self.events.append(event)
        if self.session.finished:
            try:
                self.store.record_match(self.match_id, self.config, self.session, self.events)
            except (OSError, sqlite3.Error) as error:
                self.storage_error = f"Match completed, but history could not be saved: {error}"
            self.audio.play("win")
        elif event.bonus:
            self.audio.play("bonus")
        elif 1 in event.outcomes:
            self.audio.play("sow")
        self.refresh_game()
        if self.session.finished:
            self.cancel_pending()
            self.pending = self.root.after(650, self._finish_match)

    def _finish_match(self):
        self.pending = None
        if self.screen == "game" and self.session.finished:
            self.show_winner()

    def show_winner(self):
        if not self.session or not self.session.finished:
            return
        self.clear("winner")
        winner = self.session.winner
        self.label(self.body, "MATCH COMPLETE", 10, bold=True, fg=self.palette.accent).pack(anchor="w", pady=(10, 12))
        self.label(self.body, f"{self.config.names[winner]} wins.", 34, bold=True).pack(anchor="w")
        self.label(self.body, f"The race is over in {len(self.events)} turns. Ready for another round?", 12, fg=self.palette.muted).pack(anchor="w", pady=(10, 26))
        cards = tk.Frame(self.body, bg=self.palette.bg)
        cards.pack(fill="x")
        for player in (0, 1):
            cards.columnconfigure(player, weight=1, uniform="winner")
            card = self.panel(cards)
            card.grid(row=0, column=player, sticky="nsew", padx=(0, 10) if player == 0 else (10, 0))
            inside = tk.Frame(card, bg=self.palette.panel)
            inside.pack(fill="both", expand=True, padx=26, pady=24)
            self.label(inside, "WINNER" if player == winner else "WELL PLAYED", 9, fg=self.palette.accent if player == winner else self.palette.muted).pack(anchor="w")
            self.label(inside, self.config.names[player], 19, bold=True).pack(anchor="w", pady=(10, 4))
            self.label(inside, str(self.session.scores[player]), 54, bold=True, fg=self.palette.accent if player == winner else self.palette.text).pack(anchor="w")
            turns = [event for event in self.events if event.player == player]
            stats = [("Turns played", len(turns)), ("Sow Sad", sum(1 in event.outcomes for event in turns)),
                     ("Zero-dice turns", sum(event.num_rolls == 0 for event in turns)),
                     ("Sus Fuss bonuses", sum(event.bonus > 0 for event in turns))]
            for title, count in stats:
                row = tk.Frame(inside, bg=self.palette.panel)
                row.pack(fill="x", pady=5)
                self.label(row, title, 10, fg=self.palette.muted).pack(side="left")
                self.label(row, str(count), 11, bold=True).pack(side="right")
        actions = tk.Frame(self.body, bg=self.palette.bg)
        actions.pack(fill="x", pady=(24, 0))
        self.button(actions, "Play again", lambda: self.start_match(self.config)).pack(side="left")
        self.button(actions, "New setup", lambda: self.show_setup(self.config.num_players), kind="secondary").pack(side="left", padx=12)
        self.button(actions, "Review final table", self.build_game, kind="secondary").pack(side="left")
        self.button(actions, "Replay", lambda: self.show_replay(self.match_id), kind="secondary").pack(side="left", padx=10)
        self.button(actions, "Statistics", self.show_statistics, kind="secondary").pack(side="left")
        self.button(actions, "Review", lambda: self.show_review(self.match_id), kind="secondary").pack(side="left", padx=10)
        seed_note = "A fixed seed restarts the same dice sequence on replay." if self.config.seed is not None else "No seed selected: each new match uses a fresh dice sequence."
        self.label(self.body, seed_note, 9, fg=self.palette.muted).pack(anchor="w", pady=(18, 0))

    def close_analysis(self):
        self._redraw_insights = None
        self.replay_playing = False
        if self.analysis_pending is not None:
            self.root.after_cancel(self.analysis_pending)
            self.analysis_pending = None
        if self.analysis_window is not None and self.analysis_window.winfo_exists():
            self.analysis_window.destroy()
        self.analysis_window = None

    def _resize_text(self):
        def resize(widget):
            if "font" in widget.keys():
                if not hasattr(widget, "_hog_base_font"):
                    actual = tkfont.Font(root=self.root, font=widget.cget("font")).actual()
                    widget._hog_base_font = (actual["family"], actual["size"], actual["weight"])
                family, size, weight = widget._hog_base_font
                display_size = size + 2 if self.preferences.large_text and 0 < size <= 13 else size
                widget.configure(font=(family, display_size, weight))
            for child in widget.winfo_children():
                resize(child)
        resize(self.root)

    def set_large_text(self, enabled):
        self.preferences = replace(self.preferences, large_text=bool(enabled))
        self._resize_text()
        self._persist_preferences()

    def show_accessibility(self):
        panel = self.analysis_shell("Accessibility")
        self.analysis_window.geometry("740x650")
        self.label(panel, "Choose comfortable presentation settings. Game rules stay unchanged.",
                   11, fg=self.palette.muted, wraplength=670).pack(anchor="w", pady=(0, 18))
        large = tk.BooleanVar(self.root, self.preferences.large_text)
        motion = tk.BooleanVar(self.root, not self.preferences.animations)
        for title, variable, command in (
                ("Larger label and control text", large, lambda: self.set_large_text(large.get())),
                ("Reduced motion / immediate dice results", motion, lambda: self.set_animations(not motion.get()))):
            tk.Checkbutton(panel, text=title, variable=variable, command=command,
                           bg=self.palette.bg, fg=self.palette.text,
                           selectcolor=self.palette.raised, activebackground=self.palette.bg,
                           activeforeground=self.palette.accent, pady=12, anchor="w").pack(fill="x")
        self.button(panel, "Use high-contrast theme", lambda: self.set_theme("contrast")).pack(anchor="w", pady=14)
        self.button(panel, "Mute all game sounds", lambda: self.set_sound(False), kind="secondary").pack(anchor="w")
        self.label(panel, "Keyboard: Tab moves focus; Enter confirms a human roll.\n"
                          "0-9 and X choose dice; P pauses; R restarts; H opens advice.\n"
                          "F1 opens rules; T switches themes; M toggles audio.\n\n"
                          "Larger text may need a wider window. Settings persist locally.",
                   11, fg=self.palette.muted, wraplength=670).pack(anchor="w", pady=22)

    def show_tutorial(self):
        panel = self.analysis_shell("Learn Hog / interactive tutorial")
        self.analysis_window.geometry("840x660")
        lessons = tutorial_lessons()
        self.tutorial_step = 0
        title = self.label(panel, "", 18, bold=True)
        title.pack(anchor="w", pady=14)
        prompt = self.label(panel, "", 13, wraplength=770)
        prompt.pack(anchor="w", pady=(0, 20))
        answers = tk.Frame(panel, bg=self.palette.bg)
        answers.pack(fill="x")
        feedback = self.label(panel, "Choose an answer to try the real scoring rule.", 12,
                              wraplength=770, fg=self.palette.accent)
        feedback.pack(anchor="w", pady=25)

        def next_step():
            self.tutorial_step += 1
            draw()
        next_button = self.button(panel, "Next lesson", next_step, state="disabled")
        next_button.pack(anchor="w")

        def draw():
            for child in answers.winfo_children():
                child.destroy()
            if self.tutorial_step == len(lessons):
                title.configure(text="Tutorial complete. Ready to play?")
                prompt.configure(text="You practiced dice totals, Sow Sad, Boar Brawl and Sus Fuss.")
                feedback.configure(text="Tutorial exercises do not change profiles or match statistics.")
                next_button.configure(text="Set up a match", state="normal", command=lambda: (self.close_analysis(), self.show_setup(1)))
                return
            name, question, options, expected, explanation = lessons[self.tutorial_step]
            title.configure(text=f"{self.tutorial_step + 1}/{len(lessons)} / {name}")
            prompt.configure(text=question)
            feedback.configure(text="Choose an answer to try the real scoring rule.")
            next_button.configure(state="disabled")

            def answer(choice):
                if choice == expected:
                    feedback.configure(text="Correct. " + explanation)
                    next_button.configure(state="normal")
                else:
                    feedback.configure(text="Try again. Think about the special rule in this question.")
            self.tutorial_answer_buttons = []
            for choice in options:
                button = self.button(answers, choice, lambda value=choice: answer(value), kind="secondary")
                button.pack(side="left", padx=(0, 14))
                self.tutorial_answer_buttons.append(button)
        self.tutorial_next_button = next_button
        draw()

    def show_practice(self):
        panel = self.analysis_shell("Practice table")
        self.analysis_window.geometry("940x760")
        self.label(panel, "Custom rules are for practice only: no history, saves, profile statistics or optimal-policy advice.",
                   10, fg=self.palette.muted, wraplength=880).pack(anchor="w", pady=(0, 12))
        controls = tk.Frame(panel, bg=self.palette.bg)
        controls.pack(fill="x")
        fields = []
        for title, initial, width in (("Goal", "50", 5), ("Your start", "0", 5),
                                      ("Computer start", "0", 5), ("Seed", "42", 8)):
            self.label(controls, title, 9).pack(side="left")
            value = tk.StringVar(self.root, initial)
            tk.Entry(controls, textvariable=value, width=width).pack(side="left", padx=6)
            fields.append(value)
        sus = tk.BooleanVar(self.root, True)
        tk.Checkbutton(panel, text="Enable Sus Fuss (Sow Sad and Boar Brawl always apply)", variable=sus,
                       bg=self.palette.bg, fg=self.palette.text, selectcolor=self.palette.raised,
                       activebackground=self.palette.bg).pack(anchor="w", pady=12)
        opponent = tk.StringVar(self.root, "always5")
        ttk.Combobox(panel, textvariable=opponent, values=("always5", "always6", "catch-up"),
                     state="readonly", style="Hog.TCombobox").pack(anchor="w")
        scoreboard = self.label(panel, "Set a goal from 20 to 200, then start practice.", 17, bold=True)
        scoreboard.pack(anchor="w", pady=18)
        canvas = tk.Canvas(panel, bg=self.palette.panel, height=100, highlightthickness=0)
        canvas.pack(fill="x")
        status = self.label(panel, "", 11, wraplength=880, fg=self.palette.accent)
        status.pack(anchor="w", pady=12)
        selection = tk.IntVar(self.root, 5)
        dice_row = tk.Frame(panel, bg=self.palette.bg)
        dice_row.pack(fill="x")
        for count in range(11):
            tk.Radiobutton(dice_row, text=str(count), variable=selection, value=count,
                           bg=self.palette.bg, fg=self.palette.text, selectcolor=self.palette.raised,
                           activebackground=self.palette.bg).pack(side="left", padx=4)
        self.practice_session = None

        def redraw(event=None):
            session = self.practice_session
            scoreboard.configure(text=f"You {session.scores[0]} : {session.scores[1]} Computer / goal {session.goal}")
            canvas.delete("all")
            if event:
                if event.outcomes:
                    for index, value in enumerate(event.outcomes):
                        draw_die(canvas, 18 + index * 67, 18, 52, value, accent=value == 1, palette=self.palette)
                else:
                    canvas.create_text(20, 45, text=f"Zero dice / Boar Brawl +{event.turn_points}",
                                       anchor="w", fill=self.palette.text, font=(self.family, 14))
                status.configure(text=f"{'You' if event.player == 0 else 'Computer'} earned {event.turn_points} points"
                                       f" and {event.bonus} Sus Fuss bonus.")
            if session.finished:
                play_button.configure(state="disabled")
                status.configure(text="Practice complete. " + ("You win." if session.winner == 0 else "Computer wins."))
            else:
                play_button.configure(state="normal" if session.current_player == 0 else "disabled")

        def cpu():
            self.analysis_pending = None
            if self.analysis_window is None or self.practice_session is None or self.practice_session.finished:
                return
            session = self.practice_session
            count = STRATEGIES[self.practice_rules.opponent][0](session.scores[1], session.scores[0])
            redraw(session.advance(count))

        def move():
            session = self.practice_session
            if session is None or session.finished or session.current_player != 0:
                return
            redraw(session.advance(selection.get()))
            if not session.finished:
                self.analysis_pending = self.root.after(450, cpu)

        def start():
            try:
                goal, own, other = (int(field.get()) for field in fields[:3])
                seed = fields[3].get().strip()
                rules = PracticeRules(goal, sus.get(), (own, other), int(seed) if seed else None, opponent.get())
            except ValueError as error:
                status.configure(text=f"Check practice settings: {error}")
                return
            if self.analysis_pending is not None:
                self.root.after_cancel(self.analysis_pending)
                self.analysis_pending = None
            self.practice_rules = rules
            self.practice_session = rules.create_session()
            canvas.delete("all")
            status.configure(text="Your turn. Practice uses immediate results.")
            redraw()
        actions = tk.Frame(panel, bg=self.palette.bg)
        actions.pack(anchor="w", pady=16)
        self.practice_start_button = self.button(actions, "Start / reset practice", start)
        self.practice_start_button.pack(side="left")
        play_button = self.button(actions, "Play selected dice", move, kind="secondary", state="disabled")
        play_button.pack(side="left", padx=12)
        self.practice_play_button = play_button

    def _profile_selected(self, seat):
        selected = self.profile_vars[seat].get()
        if self.profile_lookup.get(selected) is not None:
            self.name_vars[seat].set(selected)

    def save_current(self):
        if self.screen != "game" or self.session.finished:
            return
        if not self.paused:
            self.toggle_pause()
        try:
            self.store.save(self.config, self.session, self.events, self.match_id)
            self.status_label.configure(text="Saved. P resumes; Home > Resume saved restores it.")
        except (OSError, sqlite3.Error, ValueError, AttributeError) as error:
            self.status_label.configure(text=f"Save failed: {error}")

    def resume_saved(self):
        try:
            config, session, events, match_id = self.store.load()
        except (OSError, sqlite3.Error, ValueError) as error:
            messagebox.showinfo("Resume saved match", str(error), parent=self.root)
            return
        self.cancel_pending()
        self.close_analysis()
        self.config, self.session, self.events, self.match_id = config, session, events, match_id
        self.selected_count = 5
        self.build_game()
        self.toggle_pause()

    def _export_history(self):
        path = filedialog.asksaveasfilename(parent=self.analysis_window, defaultextension=".csv",
                                          initialfile="hog-history.csv", filetypes=(("CSV", "*.csv"),))
        if path:
            try:
                self.store.export_history(path)
                self.hub_status.configure(text="History exported.")
            except (OSError, sqlite3.Error) as error:
                self.hub_status.configure(text=f"Export failed: {error}")

    def show_player_hub(self):
        panel = self.analysis_shell("Player hub")
        self.analysis_window.geometry("960x760")
        self.hub_status = self.label(panel, self.storage_error or "Profiles are local. Guest matches enter history without profile statistics.",
                                      10, fg=self.palette.muted, wraplength=900)
        self.hub_status.pack(anchor="w", pady=(0, 12))
        create = tk.Frame(panel, bg=self.palette.bg)
        create.pack(fill="x", pady=(0, 12))
        name = tk.StringVar(self.root)
        tk.Entry(create, textvariable=name, width=25).pack(side="left", ipady=6)

        def add():
            try:
                self.store.create_profile(name.get())
                self.show_player_hub()
            except (ValueError, sqlite3.Error) as error:
                self.hub_status.configure(text=str(error))
        self.button(create, "Create profile", add).pack(side="left", padx=10)
        self.button(create, "Export history CSV", self._export_history, kind="secondary").pack(side="right")
        self.button(create, "Replay viewer", self.show_replay, kind="secondary").pack(side="right", padx=8)
        self.button(create, "Statistics", self.show_statistics, kind="secondary").pack(side="right")
        notebook = ttk.Notebook(panel)
        notebook.pack(fill="both", expand=True)
        self.hub_tabs = {}
        for title in ("Profiles & achievements", "Match history", "Leaderboard"):
            page = tk.Frame(notebook, bg=self.palette.panel)
            notebook.add(page, text=title)
            self.hub_tabs[title] = page
        profiles = self.hub_tabs["Profiles & achievements"]
        listing = tk.Listbox(profiles, bg=self.palette.panel, fg=self.palette.text,
                              selectbackground=self.palette.accent, selectforeground=self.palette.accent_text,
                              width=24, relief="flat", exportselection=False)
        listing.pack(side="left", fill="y", padx=16, pady=16)
        details = self.label(profiles, "Create a profile, then select it here.\nAssign it to a human seat in Match setup.",
                             12, wraplength=570)
        details.pack(side="left", anchor="n", padx=16, pady=24)
        rows = self.store.stats()
        for row in rows:
            listing.insert("end", row["name"])

        def selected(_event=None):
            if not listing.curselection():
                return
            row = rows[listing.curselection()[0]]
            achievements = self.store.achievements(row["id"])
            text = (f"{row['name']}\n\nMatches: {row['played']}  |  Wins: {row['wins']}  |  Losses: {row['played'] - row['wins']}\n"
                    f"Best score: {row['best_score']}\n\nACHIEVEMENTS\n")
            text += "\n".join(f"{'UNLOCKED' if unlocked else 'LOCKED'} / {title}" for title, unlocked in achievements)
            details.configure(text=text)
        listing.bind("<<ListboxSelect>>", selected)
        if rows:
            listing.selection_set(0)
            selected()
        history = tk.Text(self.hub_tabs["Match history"], bg=self.palette.panel, fg=self.palette.text,
                           relief="flat", wrap="word", padx=18, pady=16)
        history.pack(fill="both", expand=True)
        matches = self.store.history()
        for row in matches[:100]:
            record = json.loads(row["payload"])
            names, scores = record["config"]["names"], record["scores"]
            history.insert("end", f"{row['finished_at']}\n{names[0]} {scores[0]} : {scores[1]} {names[1]}"
                           f" / {len(record['events'])} turns\n\n")
        if not matches:
            history.insert("end", "No completed matches yet.")
        history.configure(state="disabled")
        board = self.hub_tabs["Leaderboard"]
        self.label(board, "LOCAL PROFILES / sorted by wins, then matches played, then name", 10,
                   fg=self.palette.muted).pack(anchor="w", padx=18, pady=18)
        ranking = tk.Text(board, bg=self.palette.panel, fg=self.palette.text, relief="flat",
                          wrap="word", padx=18, pady=8, font=(self.family, 12))
        ranking.pack(fill="both", expand=True)
        for rank, row in enumerate(rows, 1):
            rate = row["wins"] / row["played"] if row["played"] else 0
            ranking.insert("end", f"{rank:02d}  {row['name']} / {row['wins']} wins / {row['played']} matches / {rate:.0%}\n\n")
        ranking.configure(state="disabled")

    def show_tournament(self):
        panel = self.analysis_shell("Computer tournament")
        self.analysis_window.geometry("960x760")
        controls = tk.Frame(panel, bg=self.palette.bg)
        controls.pack(fill="x")
        self.label(controls, "Games per seat", 10).pack(side="left")
        games = tk.StringVar(self.root, "10")
        tk.Entry(controls, textvariable=games, width=5).pack(side="left", padx=8)
        self.label(controls, "Seed", 10).pack(side="left")
        seed = tk.StringVar(self.root, "42")
        tk.Entry(controls, textvariable=seed, width=8).pack(side="left", padx=8)
        content = tk.Frame(panel, bg=self.palette.bg)
        content.pack(fill="x", pady=16)
        choices = tk.Listbox(content, selectmode="multiple", exportselection=False, width=18, height=10,
                              bg=self.palette.panel, fg=self.palette.text,
                              selectbackground=self.palette.accent, selectforeground=self.palette.accent_text)
        choices.pack(side="left", fill="y", padx=(0, 14))
        keys = tuple(STRATEGIES)
        for index, key in enumerate(keys):
            choices.insert("end", key)
            if key in ("always5", "adaptive", "sus", "medium", "hard"):
                choices.selection_set(index)
        chart = tk.Canvas(content, height=340, width=680, bg=self.palette.panel, highlightthickness=0)
        chart.pack(side="left", fill="x", expand=True)
        self.analysis_status = self.label(panel, "Select 2-9 strategies. Every pair plays both starting seats equally.",
                                          10, wraplength=900, fg=self.palette.muted)
        self.analysis_status.pack(anchor="w", pady=(0, 12))
        self.tournament_result = None
        self.tournament_chart = chart

        def display(result):
            self.tournament_result = result
            chart.delete("all")
            for index, row in enumerate(result["standings"]):
                y = 12 + index * 34
                rate = row["wins"] / row["played"]
                chart.create_text(12, y + 10, text=row["strategy"], anchor="w", fill=self.palette.text)
                chart.create_rectangle(100, y, 100 + 340 * rate, y + 22, fill=self.palette.accent, outline="")
                chart.create_text(460, y + 10, text=f"{row['wins']}/{row['played']}  {rate:.0%}",
                                  anchor="w", fill=self.palette.text)
            self.analysis_status.configure(text=f"{len(result['matches'])} matches / seed {result['seed']} / "
                "rank by wins, then point difference, then strategy name. Profiles are unaffected.")
            export_button.configure(state="normal")
            run_button.configure(state="normal")

        def run():
            try:
                count, seed_value = int(games.get()), int(seed.get())
                selected_keys = tuple(keys[index] for index in choices.curselection())
                if not 1 <= count <= 200 or len(selected_keys) < 2:
                    raise ValueError
            except ValueError:
                self.analysis_status.configure(text="Choose at least two strategies, 1-200 games per seat, and an integer seed.")
                return
            run_button.configure(state="disabled")
            self.analysis_status.configure(text="Running the round robin in the background...")

            def ready(result):
                try:
                    self.store.save_tournament(result)
                except sqlite3.Error as error:
                    self.storage_error = f"Tournament results could not be saved: {error}"
                display(result)
            self.poll_analysis(self.worker.submit(run_tournament, selected_keys, count, seed_value), ready)

        def export():
            path = filedialog.asksaveasfilename(parent=self.analysis_window, defaultextension=".csv",
                                               initialfile="hog-tournament.csv", filetypes=(("CSV", "*.csv"),))
            if path and self.tournament_result:
                try:
                    export_tournament(path, self.tournament_result)
                    self.analysis_status.configure(text="Tournament match results exported.")
                except OSError as error:
                    self.analysis_status.configure(text=f"Export failed: {error}")
        run_button = self.button(controls, "Run tournament", run)
        run_button.pack(side="right")
        self.tournament_run_button = run_button
        export_button = self.button(panel, "Export tournament CSV", export, kind="secondary", state="disabled")
        export_button.pack(anchor="w", pady=(4, 12))
        saved = self.store.tournaments()
        if saved:
            labels = [f"{row['created_at']} / {row['id'][:8]}" for row in saved]
            recent = tk.StringVar(self.root, labels[0])
            combo = ttk.Combobox(panel, textvariable=recent, values=labels, state="readonly",
                                 style="Hog.TCombobox")
            combo.pack(fill="x")
            combo.bind("<<ComboboxSelected>>", lambda _event: display(json.loads(saved[labels.index(recent.get())]["payload"])))
            self.label(panel, "Previously saved tournament / choose to reopen", 9,
                       fg=self.palette.muted).pack(anchor="w", pady=8)
            display(json.loads(saved[0]["payload"]))

    def analysis_shell(self, title):
        self.close_analysis()
        window = tk.Toplevel(self.root)
        self.analysis_window = window
        window.title(title)
        window.geometry("860x720")
        window.configure(bg=self.palette.bg)
        window.transient(self.root)
        window.protocol("WM_DELETE_WINDOW", self.close_analysis)
        inside = tk.Frame(window, bg=self.palette.bg)
        inside.pack(fill="both", expand=True, padx=26, pady=22)
        self.label(inside, title, 23, bold=True).pack(anchor="w", pady=(0, 12))
        if self.preferences.large_text:
            self.root.after_idle(self._resize_text)
        return inside

    def poll_analysis(self, future, callback):
        self.analysis_pending = None
        if self.analysis_window is None or not self.analysis_window.winfo_exists():
            return
        if not future.done():
            self.analysis_pending = self.root.after(30, lambda: self.poll_analysis(future, callback))
            return
        try:
            result = future.result()
        except Exception as error:
            self.analysis_status.configure(text=f"Analysis could not complete: {error}")
            return
        callback(result)

    def show_advice(self):
        self.show_coach()

    def show_comparison(self):
        panel = self.analysis_shell("Strategy comparison")
        controls = tk.Frame(panel, bg=self.palette.bg)
        controls.pack(fill="x")
        self.label(controls, "Games per seat", 10).pack(side="left")
        games = tk.StringVar(self.root, "40")
        tk.Entry(controls, textvariable=games, width=6).pack(side="left", padx=8)
        self.label(controls, "Baseline", 10).pack(side="left")
        baseline = tk.StringVar(self.root, "adaptive")
        ttk.Combobox(controls, textvariable=baseline, values=tuple(STRATEGIES), width=11,
                     state="readonly", style="Hog.TCombobox").pack(side="left", padx=8)
        chart = tk.Canvas(panel, height=360, bg=self.palette.panel, highlightthickness=0)
        chart.pack(fill="x", pady=18)
        self.analysis_status = self.label(panel, "Run a measured comparison. Seed: 42. Equal games in both starting seats.",
                                          10, wraplength=790, fg=self.palette.muted)
        self.analysis_status.pack(anchor="w")

        def run():
            try:
                count = int(games.get())
                if not 1 <= count <= 2000:
                    raise ValueError
            except ValueError:
                self.analysis_status.configure(text="Enter 1-2000 games per seat.")
                return
            chosen = baseline.get()
            run_button.configure(state="disabled")
            self.analysis_status.configure(text="Simulating matches in the background...")

            def ready(rows):
                run_button.configure(state="normal")
                chart.delete("all")
                for index, (key, first, second, rate, low, high) in enumerate(rows):
                    y = 20 + index * 52
                    chart.create_text(15, y + 12, text=key, anchor="w", fill=self.palette.text)
                    chart.create_rectangle(110, y, 110 + 450 * rate, y + 25,
                                           fill=self.palette.accent, outline="")
                    chart.create_line(110 + 450 * low, y + 13, 110 + 450 * high, y + 13,
                                      fill=self.palette.gold, width=3)
                    chart.create_text(585, y + 12, text=f"{rate:.1%}  ({first}+{second} wins)",
                                      anchor="w", fill=self.palette.text)
                self.analysis_status.configure(text=f"Baseline: {chosen}. {count * 2} games per candidate, seed 42. "
                    "Gold lines: approximate 95% Wilson intervals. Estimates are not guarantees.")
            self.poll_analysis(self.worker.submit(compare_opponents, count, 42, chosen), ready)
        run_button = self.button(controls, "Run comparison", run)
        run_button.pack(side="right")
        self.comparison_run_button = run_button

    def show_rules(self):
        if self.rules_window is not None and self.rules_window.winfo_exists():
            self.rules_window.lift()
            return
        window = tk.Toplevel(self.root)
        self.rules_window = window
        window.title("How to play Hog")
        window.geometry("660x670")
        window.minsize(640, 640)
        window.configure(bg=self.palette.bg)
        window.transient(self.root)
        inner = tk.Frame(window, bg=self.palette.bg)
        inner.pack(fill="both", expand=True, padx=30, pady=26)
        self.label(inner, "KNOW THE RULES", 9, fg=self.palette.accent).pack(anchor="w")
        self.label(inner, "Three rules. One goal.", 25, bold=True).pack(anchor="w", pady=(10, 18))
        sections = [
            ("01 / Race to 100", "Player 0 starts. Take turns choosing 0-10 dice. Be first to end a turn with at least 100 points, after all bonuses."),
            ("02 / Sow Sad", "Any rolled 1 makes your turn worth only 1 point. Otherwise, earn the sum of all dice. All chosen dice are rolled."),
            ("03 / Boar Brawl", "Choose 0 dice to gain max(1, 3 x abs(opponent tens digit - your ones digit)). Your score 21 vs 46 earns 9 points."),
            ("04 / Sus Fuss", "After adding turn points, a total with exactly 3 or 4 positive factors increases to the next larger prime. A total of 21 becomes 23. This also applies after choosing 0 dice."),
        ]
        for title, description in sections:
            self.label(inner, title, 12, bold=True, fg=self.palette.gold).pack(anchor="w", pady=(5, 5))
            self.label(inner, description, 11, fg=self.palette.muted, wraplength=585).pack(anchor="w", pady=(0, 15))
        self.button(inner, "Got it", window.destroy).pack(anchor="w", pady=(6, 0))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hog Campaign Edition")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--theme", choices=BASE_THEMES, help="override the saved theme for launch")
    parser.add_argument("--no-animation", action="store_true", help="start with reduced motion")
    parser.add_argument("--mute", action="store_true", help="start with sound disabled")
    parser.add_argument("--smoke-test", action="store_true", help="briefly open a window using temporary data, then exit")
    args = parser.parse_args(argv)
    if tk is None:
        print("Tkinter is not installed in this Python environment.\n"
              "Install Python's Tk support, or play with: python hog_ui.py", file=sys.stderr)
        return 1
    try:
        root = tk.Tk()
    except tk.TclError as error:
        print(f"Unable to open the desktop window: {error}\n"
              "Use a local graphical desktop, or play with: python hog_ui.py", file=sys.stderr)
        return 1
    path = default_preferences_path()
    preferences = Preferences() if args.smoke_test else load_preferences(path)
    if args.theme:
        preferences = replace(preferences, theme=args.theme)
    if args.no_animation:
        preferences = replace(preferences, animations=False)
    if args.mute:
        preferences = replace(preferences, sound=False)
    app = HogApp(root, preferences=preferences, preferences_path=None if args.smoke_test else path,
                 data_path=None if args.smoke_test else path.parent / "hog.sqlite3")
    errors = []
    if args.smoke_test:
        root.report_callback_exception = lambda kind, error, trace: errors.append(error)
        root.after(1200, app.close)
    root.mainloop()
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
