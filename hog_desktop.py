"""The Game of Hog - Graphical Desktop Edition.

Run: python hog_desktop.py. Tkinter is the only UI dependency.
Canvas dice are drawn with vector shapes; no image assets are needed at runtime.
"""

import argparse
import sys
from dataclasses import fields, replace
import math
from pathlib import Path
from random import Random

try:
    import tkinter as tk
    from tkinter import font as tkfont, messagebox, ttk
except ImportError:
    tk = None

from hog import GOAL, STRATEGIES, VERSION, GameSession, seeded_dice, sus_update
from hog_match import MatchConfig
from hog_audio import SoundPlayer
from hog_preferences import (PALETTES, PACE_DELAYS, Preferences, default_preferences_path,
                             load_preferences, save_preferences)

PIPS = {
    1: ((1, 1),),
    2: ((0, 0), (2, 2)),
    3: ((0, 0), (1, 1), (2, 2)),
    4: ((0, 0), (2, 0), (0, 2), (2, 2)),
    5: ((0, 0), (2, 0), (1, 1), (0, 2), (2, 2)),
    6: ((0, 0), (0, 1), (0, 2), (2, 0), (2, 1), (2, 2)),
}


def draw_die(canvas, x, y, size, value, *, accent=False, palette=None, angle=0):
    """Vector dice; rotation is cosmetic and never changes a game outcome."""
    palette = palette or PALETTES["dark"]
    fill = ("#f4c375" if palette is PALETTES["dark"] else "#ffdc9e") if accent else palette.die
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
                           fill=palette.pip, outline="")


class HogApp:
    """Event-driven desktop views. Computer turns use cancellable Tk timers."""

    def __init__(self, root, *, cpu_delay=None, preferences=None, preferences_path=None):
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
        self.session = None
        self.config = None
        self.events = []
        self.screen = "home"
        self.rules_window = None
        root.title(f"Hog | Animated Game Edition v{VERSION}")
        height = max(720, min(820, root.winfo_screenheight() - 70))
        root.geometry(f"1160x{height}")
        root.minsize(1040, 720)
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
        self.shell.pack(fill="both", expand=True, padx=32, pady=22)
        top = tk.Frame(self.shell, bg=self.palette.bg)
        top.pack(fill="x", pady=(0, 19))
        self.label(top, "HOG", 26, bold=True, fg=self.palette.accent).pack(side="left")
        self.label(top, "  /  THE DICE GAME", 10, fg=self.palette.muted).pack(side="left", pady=(7, 0))
        self.button(top, "Rules", self.show_rules, kind="secondary").pack(side="right")
        self.button(top, "Home", self.navigate_home, kind="secondary").pack(side="right", padx=8)
        self.button(top, "Settings", self.show_settings, kind="secondary").pack(side="right", padx=(0, 8))
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
        self.show_home()

    def label(self, parent, text, size=11, *, bold=False, fg=None, bg=None, **kwargs):
        return tk.Label(parent, text=text, font=(self.family, size, "bold" if bold else "normal"),
                        bg=bg or parent.cget("bg"), fg=fg or self.palette.text, anchor="w", justify="left", **kwargs)

    def button(self, parent, text, command, *, kind="primary", **kwargs):
        fill, foreground = (self.palette.accent, self.palette.accent_text) if kind == "primary" else (self.palette.raised, self.palette.text)
        button = tk.Button(parent, text=text, command=command,
                         bg=fill, fg=foreground, activebackground=self.palette.gold,
                         activeforeground=self.palette.accent_text, disabledforeground=self.palette.disabled,
                         font=(self.family, 10, "bold"), relief="flat", bd=0,
                         padx=18, pady=10, cursor="hand2", highlightthickness=2,
                         highlightbackground=fill, highlightcolor=self.palette.gold, **kwargs)
        button._hog_kind = kind
        return button

    def panel(self, parent, **kwargs):
        return tk.Frame(parent, bg=self.palette.panel, highlightbackground=self.palette.border,
                        highlightthickness=1, **kwargs)

    def clear(self, screen):
        self.cancel_pending()
        self.animating = False
        self.paused = False
        self._visual_outcomes = ()
        self.screen = screen
        for child in self.body.winfo_children():
            child.destroy()

    def cancel_pending(self):
        if self.pending is not None:
            self.root.after_cancel(self.pending)
            self.pending = None

    def close(self):
        self.cancel_pending()
        self.audio.stop()
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
                        "selectbackground", "selectforeground", "disabledforeground", "selectcolor"):
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
        style = ttk.Style(self.root)
        style.configure("Hog.TCombobox", fieldbackground=new.bg, background=new.raised,
                        foreground=new.text, arrowcolor=new.accent)
        style.map("Hog.TCombobox", fieldbackground=[("disabled", new.raised), ("readonly", new.bg)],
                  foreground=[("disabled", new.muted), ("readonly", new.text)])
        self.root.option_add("*TCombobox*Listbox.background", new.panel)
        self.root.option_add("*TCombobox*Listbox.foreground", new.text)
        self.theme_button.configure(text="Light mode" if theme == "dark" else "Dark mode")
        if self.screen == "game":
            self.refresh_game()
        self._sync_settings()
        self._persist_preferences()

    def toggle_theme(self):
        self.set_theme("light" if self.preferences.theme == "dark" else "dark")

    def set_animations(self, enabled):
        self.preferences = replace(self.preferences, animations=bool(enabled))
        if self.animating and not self.paused and not self.preferences.animations:
            self.cancel_pending()
            self.finish_roll()
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
        theme = ttk.Combobox(inner, textvariable=self.settings_theme, values=tuple(PALETTES),
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
            else:
                return None
        else:
            return None
        return "break"

    def show_home(self):
        self.clear("home")
        hero = self.panel(self.body)
        hero.pack(fill="x", pady=(0, 18))
        copy = tk.Frame(hero, bg=self.palette.panel)
        copy.pack(side="left", fill="both", expand=True, padx=30, pady=28)
        self.label(copy, "THE CLASSIC GAME. A NEW WAY TO PLAY.", 9, fg=self.palette.accent).pack(anchor="w")
        self.label(copy, "A little luck.\nA better decision.", 33, bold=True).pack(anchor="w", pady=(12, 10))
        self.label(copy, "Roll the dice, take the free points, and race to 100.\n"
                        "Three special rules. Plenty of ways to win.", 12, fg=self.palette.muted).pack(anchor="w")
        self.button(copy, "Start a match  >", lambda: self.show_setup(1)).pack(anchor="w", pady=(22, 0))
        art = tk.Canvas(hero, width=305, height=284, bg=self.palette.panel, highlightthickness=0)
        art.pack(side="right", padx=(0, 24), pady=20)
        art.create_oval(25, 12, 290, 277, fill=self.palette.hero, outline="")
        draw_die(art, 47, 51, 112, 5, palette=self.palette)
        draw_die(art, 165, 128, 96, 3, palette=self.palette)
        art.create_text(155, 257, text="THE RACE TO 100", font=(self.family, 10, "bold"), fill=self.palette.accent)
        self.label(self.body, "CHOOSE YOUR TABLE", 10, bold=True, fg=self.palette.muted).pack(anchor="w", pady=(0, 10))
        modes = tk.Frame(self.body, bg=self.palette.bg)
        modes.pack(fill="both", expand=True)
        options = [(1, "01  /  SOLO", "You vs computer", "Choose a strategy to challenge.\nYour moves. Your decisions."),
                   (2, "02  /  LOCAL", "Pass & play", "Two people, one screen.\nTake turns choosing your dice."),
                   (0, "03  /  WATCH", "Strategy showdown", "Let two computer strategies\nplay a complete match.")]
        for column, (mode, eyebrow, title, description) in enumerate(options):
            modes.columnconfigure(column, weight=1, uniform="cards")
            card = self.panel(modes)
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0 if column == 2 else 8))
            self.label(card, eyebrow, 9, fg=self.palette.gold).pack(anchor="w", padx=20, pady=(20, 12))
            self.label(card, title, 17, bold=True).pack(anchor="w", padx=20)
            self.label(card, description, 10, fg=self.palette.muted).pack(anchor="w", padx=20, pady=(9, 16))
            self.button(card, "Choose mode", lambda chosen=mode: self.show_setup(chosen), kind="secondary").pack(anchor="w", padx=20, pady=(0, 20))
        modes.rowconfigure(0, weight=1)

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
        initial_names = ("Player 0", "Player 1" if mode == 2 else "Computer")
        if mode == 0:
            initial_names = ("Computer 0", "Computer 1")
        titles = [f"{key} / {value[1]}" for key, value in STRATEGIES.items()]
        for player in (0, 1):
            cards.columnconfigure(player, weight=1, uniform="players")
            card = self.panel(cards)
            card.grid(row=0, column=player, sticky="nsew", padx=(0, 10) if player == 0 else (10, 0))
            inner = tk.Frame(card, bg=self.palette.panel)
            inner.pack(fill="both", expand=True, padx=25, pady=22)
            self.label(inner, f"PLAYER {player}", 9, fg=self.palette.accent if player == 0 else self.palette.gold).pack(anchor="w")
            control = self.label(inner, "", 16, bold=True)
            control.pack(anchor="w", pady=(7, 18))
            self.control_labels.append(control)
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
            hint = self.label(inner, "", 9, fg=self.palette.muted, wraplength=390, height=3)
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
            key = self.strategy_vars[player].get().split(" / ")[0]
            hint = "You choose the dice on each turn." if human else STRATEGIES[key][2]
            self.strategy_hints[player].configure(text=hint)

    def _begin_from_setup(self):
        try:
            seed = self.seed_var.get().strip()
            config = MatchConfig(self.mode_var.get(),
                                 tuple(name.get().strip() for name in self.name_vars),
                                 tuple(strategy.get().split(" / ")[0] for strategy in self.strategy_vars),
                                 int(seed) if seed else None)
        except (ValueError, KeyError):
            self.setup_error.configure(text="Use names of 1-20 printable characters and a whole-number seed (or leave it blank).")
            return
        self.start_match(config)

    def start_match(self, config):
        self.cancel_pending()
        self.audio.stop()
        self.config = config
        self.session = GameSession(dice=seeded_dice(config.seed))
        self.events = []
        self.selected_count = 5
        self.build_game()

    def build_game(self):
        self.clear("game")
        title = tk.Frame(self.body, bg=self.palette.bg)
        title.pack(fill="x", pady=(0, 15))
        self.label(title, "THE RACE TO 100", 10, bold=True, fg=self.palette.accent).pack(side="left")
        self.turn_label = self.label(title, "", 11, fg=self.palette.muted)
        self.turn_label.pack(side="left", padx=18)
        self.restart_button = self.button(title, "Restart / R", self.restart_match, kind="secondary")
        self.restart_button.configure(pady=5, padx=10, font=(self.family, 9, "bold"))
        self.restart_button.pack(side="right")
        self.pause_button = self.button(title, "Pause / P", self.toggle_pause, kind="secondary")
        self.pause_button.configure(pady=5, padx=10, font=(self.family, 9, "bold"))
        self.pause_button.pack(side="right", padx=8)
        scores = tk.Frame(self.body, bg=self.palette.bg)
        scores.pack(fill="x", pady=(0, 18))
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
            self.label(score_row, control, 8, fg=self.palette.muted).pack(side="right", pady=(15, 0))
            self.score_labels.append(score)
            bar = tk.Canvas(inside, height=5, bg=self.palette.raised, highlightthickness=0)
            bar.pack(fill="x")
            bar.bind("<Configure>", lambda _event: self._redraw_bars())
            self.score_bars.append(bar)
        table = tk.Frame(self.body, bg=self.palette.bg)
        table.pack(fill="both", expand=True)
        left = self.panel(table)
        left.pack(side="left", fill="both", expand=True, padx=(0, 18))
        inner = tk.Frame(left, bg=self.palette.panel)
        inner.pack(fill="both", expand=True, padx=22, pady=18)
        self.label(inner, "ON THE TABLE", 9, fg=self.palette.muted, bold=True).pack(anchor="w")
        self.dice_canvas = tk.Canvas(inner, bg=self.palette.panel, height=105, highlightthickness=0)
        self.dice_canvas.pack(fill="x", pady=(8, 0))
        self.dice_canvas.bind("<Configure>", lambda _event: self._draw_outcomes())
        self.result_label = self.label(inner, "", 12, bold=True, wraplength=600, height=1)
        self.result_label.pack(anchor="w", fill="x", pady=(0, 3))
        self.bonus_label = self.label(inner, "", 10, fg=self.palette.accent, wraplength=600, height=1)
        self.bonus_label.pack(anchor="w", fill="x")
        self.label(inner, "CHOOSE YOUR DICE", 9, fg=self.palette.muted, bold=True).pack(anchor="w", pady=(12, 9))
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
        self.free_label.pack(anchor="w", pady=(12, 12))
        action_row = tk.Frame(inner, bg=self.palette.panel)
        action_row.pack(fill="x")
        self.action_button = self.button(action_row, "", self.roll_human)
        self.action_button.pack(side="left")
        self.status_label = self.label(action_row, "", 9, fg=self.palette.muted, wraplength=280)
        self.status_label.pack(side="left", padx=15)
        right = self.panel(table, width=290)
        right.pack(side="right", fill="y")
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
        self.refresh_game()

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
                         size, value, palette=self.palette, angle=math.sin(phase) * 13)
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
            draw_die(canvas, start + index * spacing, 18, size, value, accent=value == 1, palette=self.palette)

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
            self.free_label.configure(text=f"Zero dice guarantees +{gain} points, including any Sus Fuss bonus.")
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
            self.active_labels[player].configure(text=indicator if active else "")
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
        self._draw_outcomes()
        self._redraw_bars()
        self._refresh_controls()
        self.journal.configure(state="normal")
        self.journal.delete("1.0", "end")
        if not self.events:
            self.journal.insert("end", "Match ready.\nPlayer 0 goes first.\n")
        for event in self.events:
            bonus = f" +{event.bonus} bonus" if event.bonus else ""
            self.journal.insert("end", f"{event.number:02d}  {self.config.names[event.player]}\n"
                                f"{event.num_rolls} dice / +{event.turn_points}{bonus}\n"
                                f"Total: {event.score_after}\n\n")
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
        seed_note = "A fixed seed restarts the same dice sequence on replay." if self.config.seed is not None else "No seed selected: each new match uses a fresh dice sequence."
        self.label(self.body, seed_note, 9, fg=self.palette.muted).pack(anchor="w", pady=(18, 0))

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
    parser = argparse.ArgumentParser(description="Hog Animated Game Edition")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("--theme", choices=tuple(PALETTES), help="override the saved theme for launch")
    parser.add_argument("--no-animation", action="store_true", help="start with reduced motion")
    parser.add_argument("--mute", action="store_true", help="start with sound disabled")
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
    preferences = load_preferences(path)
    if args.theme:
        preferences = replace(preferences, theme=args.theme)
    if args.no_animation:
        preferences = replace(preferences, animations=False)
    if args.mute:
        preferences = replace(preferences, sound=False)
    HogApp(root, preferences=preferences, preferences_path=path)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
