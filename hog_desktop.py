"""The Game of Hog - Graphical Desktop Edition.

Run: python hog_desktop.py. Tkinter is the only UI dependency.
Canvas dice are drawn with vector shapes; no image assets are needed at runtime.
"""

import argparse
import sys

try:
    import tkinter as tk
    from tkinter import font as tkfont, messagebox, ttk
except ImportError:
    tk = None

from hog import GOAL, STRATEGIES, VERSION, GameSession, seeded_dice, sus_update
from hog_match import MatchConfig

BG = "#0d1626"
PANEL = "#17243a"
RAISED = "#20324c"
BORDER = "#30445e"
TEXT = "#eef3f8"
MUTED = "#a3b4ca"
MINT = "#85e0ba"
MINT_DARK = "#182f2d"
GOLD = "#f4c375"
RED = "#ff9c9c"

PIPS = {
    1: ((1, 1),),
    2: ((0, 0), (2, 2)),
    3: ((0, 0), (1, 1), (2, 2)),
    4: ((0, 0), (2, 0), (0, 2), (2, 2)),
    5: ((0, 0), (2, 0), (1, 1), (0, 2), (2, 2)),
    6: ((0, 0), (0, 1), (0, 2), (2, 0), (2, 1), (2, 2)),
}


def draw_die(canvas, x, y, size, value, *, accent=False):
    """Draw one actual outcome. Accent a 1 so Sow Sad is easy to identify."""
    fill = "#f4c375" if accent else "#eff5f4"
    canvas.create_rectangle(x + 3, y + 4, x + size + 3, y + size + 4,
                            fill="#0b1220", outline="")
    canvas.create_rectangle(x, y, x + size, y + size, fill=fill, outline=fill)
    radius = size * 0.062
    for column, row in PIPS[value]:
        cx, cy = x + size * (0.26 + column * 0.24), y + size * (0.26 + row * 0.24)
        canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius,
                           fill=BG, outline="")


class HogApp:
    """Event-driven desktop views. Computer turns use cancellable Tk timers."""

    def __init__(self, root, *, cpu_delay=850):
        self.root = root
        self.cpu_delay = cpu_delay
        self.pending = None
        self.session = None
        self.config = None
        self.events = []
        self.screen = "home"
        self.rules_window = None
        root.title(f"Hog | Desktop Edition v{VERSION}")
        height = max(720, min(820, root.winfo_screenheight() - 70))
        root.geometry(f"1160x{height}")
        root.minsize(1040, 720)
        root.configure(bg=BG)
        root.protocol("WM_DELETE_WINDOW", self.close)
        families = tkfont.families(root)
        self.family = next((family for family in ("Segoe UI", "DejaVu Sans", "Helvetica")
                            if family in families), "TkDefaultFont")
        root.option_add("*Font", (self.family, 10))
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("Hog.TCombobox", fieldbackground=BG, background=RAISED,
                        foreground=TEXT, arrowcolor=MINT, padding=8)
        style.map("Hog.TCombobox", fieldbackground=[("readonly", BG)],
                  foreground=[("readonly", TEXT), ("disabled", MUTED)])
        root.option_add("*TCombobox*Listbox.background", PANEL)
        root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.shell = tk.Frame(root, bg=BG)
        self.shell.pack(fill="both", expand=True, padx=32, pady=22)
        top = tk.Frame(self.shell, bg=BG)
        top.pack(fill="x", pady=(0, 19))
        self.label(top, "HOG", 26, bold=True, fg=MINT).pack(side="left")
        self.label(top, "  /  THE DICE GAME", 10, fg=MUTED).pack(side="left", pady=(7, 0))
        self.button(top, "Rules", self.show_rules, kind="secondary").pack(side="right")
        self.button(top, "Home", self.navigate_home, kind="secondary").pack(side="right", padx=8)
        self.label(top, f"DESKTOP EDITION  /  v{VERSION}", 9, fg=MUTED).pack(side="right", padx=16)
        self.body = tk.Frame(self.shell, bg=BG)
        self.body.pack(fill="both", expand=True)
        footer = tk.Frame(self.shell, bg=BG)
        footer.pack(fill="x", pady=(14, 0))
        self.label(footer, "LOCAL PLAY   /   2 PLAYERS   /   FIRST TO 100", 8, fg=MUTED).pack(side="left")
        self.label(footer, "A little luck. A better decision.", 9, fg=MINT).pack(side="right")
        root.bind("<Return>", self._enter_roll)
        self.show_home()

    def label(self, parent, text, size=11, *, bold=False, fg=TEXT, bg=None, **kwargs):
        return tk.Label(parent, text=text, font=(self.family, size, "bold" if bold else "normal"),
                        bg=bg or parent.cget("bg"), fg=fg, anchor="w", justify="left", **kwargs)

    def button(self, parent, text, command, *, kind="primary", **kwargs):
        fill, foreground = (MINT, BG) if kind == "primary" else (RAISED, TEXT)
        return tk.Button(parent, text=text, command=command,
                         bg=fill, fg=foreground, activebackground=GOLD,
                         activeforeground=BG, disabledforeground="#6f829a",
                         font=(self.family, 10, "bold"), relief="flat", bd=0,
                         padx=18, pady=10, cursor="hand2", highlightthickness=2,
                         highlightbackground=fill, highlightcolor=GOLD, **kwargs)

    def panel(self, parent, **kwargs):
        return tk.Frame(parent, bg=PANEL, highlightbackground=BORDER,
                        highlightthickness=1, **kwargs)

    def clear(self, screen):
        self.cancel_pending()
        self.screen = screen
        for child in self.body.winfo_children():
            child.destroy()

    def cancel_pending(self):
        if self.pending is not None:
            self.root.after_cancel(self.pending)
            self.pending = None

    def close(self):
        self.cancel_pending()
        self.root.destroy()

    def navigate_home(self):
        if self.session and not self.session.finished and self.screen == "game":
            if not messagebox.askyesno("Leave match?", "Return home and leave this unfinished match?",
                                       parent=self.root):
                return
        self.session = None
        self.show_home()

    def show_home(self):
        self.clear("home")
        hero = self.panel(self.body)
        hero.pack(fill="x", pady=(0, 18))
        copy = tk.Frame(hero, bg=PANEL)
        copy.pack(side="left", fill="both", expand=True, padx=30, pady=28)
        self.label(copy, "THE CLASSIC GAME. A NEW WAY TO PLAY.", 9, fg=MINT).pack(anchor="w")
        self.label(copy, "A little luck.\nA better decision.", 33, bold=True).pack(anchor="w", pady=(12, 10))
        self.label(copy, "Roll the dice, take the free points, and race to 100.\n"
                        "Three special rules. Plenty of ways to win.", 12, fg=MUTED).pack(anchor="w")
        self.button(copy, "Start a match  >", lambda: self.show_setup(1)).pack(anchor="w", pady=(22, 0))
        art = tk.Canvas(hero, width=305, height=284, bg=PANEL, highlightthickness=0)
        art.pack(side="right", padx=(0, 24), pady=20)
        art.create_oval(25, 12, 290, 277, fill="#1d3b3a", outline="")
        draw_die(art, 47, 51, 112, 5)
        draw_die(art, 165, 128, 96, 3)
        art.create_text(155, 257, text="THE RACE TO 100", font=(self.family, 10, "bold"), fill=MINT)
        self.label(self.body, "CHOOSE YOUR TABLE", 10, bold=True, fg=MUTED).pack(anchor="w", pady=(0, 10))
        modes = tk.Frame(self.body, bg=BG)
        modes.pack(fill="both", expand=True)
        options = [(1, "01  /  SOLO", "You vs computer", "Choose a strategy to challenge.\nYour moves. Your decisions."),
                   (2, "02  /  LOCAL", "Pass & play", "Two people, one screen.\nTake turns choosing your dice."),
                   (0, "03  /  WATCH", "Strategy showdown", "Let two computer strategies\nplay a complete match.")]
        for column, (mode, eyebrow, title, description) in enumerate(options):
            modes.columnconfigure(column, weight=1, uniform="cards")
            card = self.panel(modes)
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0 if column == 2 else 8))
            self.label(card, eyebrow, 9, fg=GOLD).pack(anchor="w", padx=20, pady=(20, 12))
            self.label(card, title, 17, bold=True).pack(anchor="w", padx=20)
            self.label(card, description, 10, fg=MUTED).pack(anchor="w", padx=20, pady=(9, 16))
            self.button(card, "Choose mode", lambda chosen=mode: self.show_setup(chosen), kind="secondary").pack(anchor="w", padx=20, pady=(0, 20))
        modes.rowconfigure(0, weight=1)

    def show_setup(self, mode=1):
        self.clear("setup")
        self.label(self.body, "MATCH SETUP", 9, fg=MINT).pack(anchor="w")
        self.label(self.body, "Set your table.", 30, bold=True).pack(anchor="w", pady=(6, 5))
        self.label(self.body, "Name your players and choose who makes the decisions.", 11, fg=MUTED).pack(anchor="w", pady=(0, 20))
        self.mode_var = tk.IntVar(self.root, value=mode)
        mode_row = tk.Frame(self.body, bg=BG)
        mode_row.pack(fill="x", pady=(0, 22))
        for count, title in ((1, "You vs computer"), (2, "Two human players"), (0, "Computer vs computer")):
            tk.Radiobutton(mode_row, text=title, variable=self.mode_var, value=count,
                           command=self._setup_mode_changed, bg=BG, fg=TEXT,
                           selectcolor=RAISED, activebackground=BG, activeforeground=MINT,
                           padx=14, pady=8, cursor="hand2").pack(side="left", padx=(0, 18))
        cards = tk.Frame(self.body, bg=BG)
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
            inner = tk.Frame(card, bg=PANEL)
            inner.pack(fill="both", expand=True, padx=25, pady=22)
            self.label(inner, f"PLAYER {player}", 9, fg=MINT if player == 0 else GOLD).pack(anchor="w")
            control = self.label(inner, "", 16, bold=True)
            control.pack(anchor="w", pady=(7, 18))
            self.control_labels.append(control)
            self.label(inner, "Display name", 10, fg=MUTED).pack(anchor="w", pady=(0, 6))
            name = tk.StringVar(self.root, initial_names[player])
            self.name_vars.append(name)
            entry = tk.Entry(inner, textvariable=name, bg=BG, fg=TEXT, insertbackground=MINT,
                             relief="flat", highlightthickness=1, highlightbackground=BORDER,
                             highlightcolor=MINT, font=(self.family, 12))
            entry.pack(fill="x", ipady=10, pady=(0, 18))
            self.label(inner, "Computer strategy", 10, fg=MUTED).pack(anchor="w", pady=(0, 6))
            selected = tk.StringVar(self.root, titles[0 if player == 0 else 5])
            self.strategy_vars.append(selected)
            combo = ttk.Combobox(inner, textvariable=selected, values=titles,
                                 state="readonly", style="Hog.TCombobox", font=(self.family, 10))
            combo.pack(fill="x")
            self.strategy_boxes.append(combo)
            hint = self.label(inner, "", 9, fg=MUTED, wraplength=390, height=3)
            hint.pack(anchor="w", pady=(10, 0))
            self.strategy_hints.append(hint)
            combo.bind("<<ComboboxSelected>>", lambda _event: self._setup_mode_changed())
        bottom = tk.Frame(self.body, bg=BG)
        bottom.pack(fill="x", pady=(24, 0))
        self.label(bottom, "Optional random seed", 10, fg=MUTED).pack(side="left")
        self.seed_var = tk.StringVar(self.root)
        tk.Entry(bottom, textvariable=self.seed_var, width=15, bg=PANEL, fg=TEXT,
                 insertbackground=MINT, relief="flat").pack(side="left", padx=14, ipady=9)
        self.label(bottom, "Leave blank for a new dice sequence.", 9, fg=MUTED).pack(side="left")
        self.button(bottom, "Begin match  >", self._begin_from_setup).pack(side="right")
        self.setup_error = self.label(self.body, "", 10, fg=RED, wraplength=1000)
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
        self.config = config
        self.session = GameSession(dice=seeded_dice(config.seed))
        self.events = []
        self.selected_count = 5
        self.build_game()

    def build_game(self):
        self.clear("game")
        title = tk.Frame(self.body, bg=BG)
        title.pack(fill="x", pady=(0, 15))
        self.label(title, "THE RACE TO 100", 10, bold=True, fg=MINT).pack(side="left")
        self.turn_label = self.label(title, "", 11, fg=MUTED)
        self.turn_label.pack(side="right")
        scores = tk.Frame(self.body, bg=BG)
        scores.pack(fill="x", pady=(0, 18))
        self.score_panels, self.score_labels, self.score_bars, self.active_labels = [], [], [], []
        for player in (0, 1):
            scores.columnconfigure(player, weight=1, uniform="scores")
            card = self.panel(scores)
            card.grid(row=0, column=player, sticky="nsew", padx=(0, 9) if player == 0 else (9, 0))
            self.score_panels.append(card)
            inside = tk.Frame(card, bg=PANEL)
            inside.pack(fill="x", padx=22, pady=14)
            top = tk.Frame(inside, bg=PANEL)
            top.pack(fill="x")
            self.label(top, self.config.names[player], 15, bold=True).pack(side="left")
            active = self.label(top, "", 9, fg=MINT)
            active.pack(side="right")
            self.active_labels.append(active)
            score_row = tk.Frame(inside, bg=PANEL)
            score_row.pack(fill="x", pady=(4, 3))
            score = self.label(score_row, "0", 38, bold=True)
            score.pack(side="left")
            self.label(score_row, " / 100", 13, fg=MUTED).pack(side="left", pady=(15, 0))
            control = "HUMAN" if self.config.is_human(player) else self.config.strategies[player].upper()
            self.label(score_row, control, 8, fg=MUTED).pack(side="right", pady=(15, 0))
            self.score_labels.append(score)
            bar = tk.Canvas(inside, height=5, bg=RAISED, highlightthickness=0)
            bar.pack(fill="x")
            bar.bind("<Configure>", lambda _event: self._redraw_bars())
            self.score_bars.append(bar)
        table = tk.Frame(self.body, bg=BG)
        table.pack(fill="both", expand=True)
        left = self.panel(table)
        left.pack(side="left", fill="both", expand=True, padx=(0, 18))
        inner = tk.Frame(left, bg=PANEL)
        inner.pack(fill="both", expand=True, padx=22, pady=18)
        self.label(inner, "ON THE TABLE", 9, fg=MUTED, bold=True).pack(anchor="w")
        self.dice_canvas = tk.Canvas(inner, bg=PANEL, height=130, highlightthickness=0)
        self.dice_canvas.pack(fill="x", pady=(8, 0))
        self.dice_canvas.bind("<Configure>", lambda _event: self._draw_outcomes())
        self.result_label = self.label(inner, "", 12, bold=True, wraplength=600, height=2)
        self.result_label.pack(anchor="w", fill="x", pady=(0, 3))
        self.bonus_label = self.label(inner, "", 10, fg=MINT, wraplength=600, height=2)
        self.bonus_label.pack(anchor="w", fill="x")
        self.label(inner, "CHOOSE YOUR DICE", 9, fg=MUTED, bold=True).pack(anchor="w", pady=(12, 9))
        selector = tk.Frame(inner, bg=PANEL)
        selector.pack(fill="x")
        self.count_buttons = []
        for count in range(11):
            selector.columnconfigure(count, weight=1, uniform="dice")
            button = self.button(selector, str(count), lambda choice=count: self.select_count(choice),
                                 kind="secondary", width=2)
            button.configure(padx=0, pady=7, font=(self.family, 10, "bold"))
            button.grid(row=0, column=count, padx=2, sticky="ew")
            self.count_buttons.append(button)
        self.free_label = self.label(inner, "", 9, fg=MUTED, wraplength=610)
        self.free_label.pack(anchor="w", pady=(12, 12))
        action_row = tk.Frame(inner, bg=PANEL)
        action_row.pack(fill="x")
        self.action_button = self.button(action_row, "", self.roll_human)
        self.action_button.pack(side="left")
        self.status_label = self.label(action_row, "", 9, fg=MUTED, wraplength=280)
        self.status_label.pack(side="left", padx=15)
        right = self.panel(table, width=290)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        self.label(right, "MATCH JOURNAL", 9, fg=MUTED, bold=True).pack(anchor="w", padx=18, pady=(18, 5))
        self.label(right, "The story so far", 15, bold=True).pack(anchor="w", padx=18, pady=(0, 14))
        history_container = tk.Frame(right, bg=PANEL)
        history_container.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        scrollbar = tk.Scrollbar(history_container, relief="flat")
        scrollbar.pack(side="right", fill="y")
        self.journal = tk.Text(history_container, bg=PANEL, fg=TEXT, font=(self.family, 10),
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
            canvas.create_rectangle(0, 0, end, 6, fill=MINT if player == 0 else GOLD, outline="")

    def _draw_outcomes(self):
        if self.screen != "game":
            return
        canvas = self.dice_canvas
        canvas.delete("all")
        width = canvas.winfo_width()
        if not self.events:
            canvas.create_text(width / 2, 61, text="Your next move starts here.",
                               fill=MUTED, font=(self.family, 14))
            return
        event = self.events[-1]
        if not event.outcomes:
            canvas.create_text(width / 2, 47, text="0 DICE. GUARANTEED POINTS.",
                               fill=MINT, font=(self.family, 14, "bold"))
            canvas.create_text(width / 2, 82, text=f"Boar Brawl +{event.turn_points}",
                               fill=TEXT, font=(self.family, 18, "bold"))
            return
        count = len(event.outcomes)
        size = min(56, max(32, (width - 16) / count - 9))
        spacing = size + 9
        start = max(0, (width - (count * spacing - 9)) / 2)
        for index, value in enumerate(event.outcomes):
            draw_die(canvas, start + index * spacing, 32, size, value, accent=value == 1)

    def select_count(self, count):
        if self.screen == "game" and not self.session.finished and self.config.is_human(self.session.current_player):
            self.selected_count = count
            self._refresh_controls()

    def _refresh_controls(self):
        finished = self.session.finished
        who = self.session.current_player
        human = not finished and self.config.is_human(who)
        for count, button in enumerate(self.count_buttons):
            selected = count == self.selected_count
            button.configure(state="normal" if human else "disabled", bg=MINT if selected else RAISED,
                             fg=BG if selected else TEXT, highlightbackground=MINT if selected else RAISED)
        if finished:
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
            self.score_panels[player].configure(highlightbackground=MINT if active else BORDER,
                                                highlightthickness=2 if active else 1)
        self.turn_label.configure(text="MATCH COMPLETE" if self.session.finished else f"TURN {self.session.turn_number:02d}")
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
        if not self.session.finished and not self.config.is_human(who) and self.pending is None:
            self.pending = self.root.after(self.cpu_delay, self.computer_turn)

    def _enter_roll(self, _event=None):
        if self.screen == "game":
            self.roll_human()

    def roll_human(self):
        if (self.screen != "game" or self.session.finished
                or not self.config.is_human(self.session.current_player)):
            return
        self.complete_turn(self.selected_count)

    def computer_turn(self):
        self.pending = None
        if (self.screen != "game" or self.session.finished
                or self.config.is_human(self.session.current_player)):
            return
        who = self.session.current_player
        strategy = STRATEGIES[self.config.strategies[who]][0]
        count = strategy(self.session.scores[who], self.session.scores[1 - who])
        self.complete_turn(count)

    def complete_turn(self, count):
        event = self.session.advance(count)
        self.events.append(event)
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
        self.label(self.body, "MATCH COMPLETE", 10, bold=True, fg=MINT).pack(anchor="w", pady=(10, 12))
        self.label(self.body, f"{self.config.names[winner]} wins.", 34, bold=True).pack(anchor="w")
        self.label(self.body, f"The race is over in {len(self.events)} turns. Ready for another round?", 12, fg=MUTED).pack(anchor="w", pady=(10, 26))
        cards = tk.Frame(self.body, bg=BG)
        cards.pack(fill="x")
        for player in (0, 1):
            cards.columnconfigure(player, weight=1, uniform="winner")
            card = self.panel(cards)
            card.grid(row=0, column=player, sticky="nsew", padx=(0, 10) if player == 0 else (10, 0))
            inside = tk.Frame(card, bg=PANEL)
            inside.pack(fill="both", expand=True, padx=26, pady=24)
            self.label(inside, "WINNER" if player == winner else "WELL PLAYED", 9, fg=MINT if player == winner else MUTED).pack(anchor="w")
            self.label(inside, self.config.names[player], 19, bold=True).pack(anchor="w", pady=(10, 4))
            self.label(inside, str(self.session.scores[player]), 54, bold=True, fg=MINT if player == winner else TEXT).pack(anchor="w")
            turns = [event for event in self.events if event.player == player]
            stats = [("Turns played", len(turns)), ("Sow Sad", sum(1 in event.outcomes for event in turns)),
                     ("Zero-dice turns", sum(event.num_rolls == 0 for event in turns)),
                     ("Sus Fuss bonuses", sum(event.bonus > 0 for event in turns))]
            for title, count in stats:
                row = tk.Frame(inside, bg=PANEL)
                row.pack(fill="x", pady=5)
                self.label(row, title, 10, fg=MUTED).pack(side="left")
                self.label(row, str(count), 11, bold=True).pack(side="right")
        actions = tk.Frame(self.body, bg=BG)
        actions.pack(fill="x", pady=(24, 0))
        self.button(actions, "Play again", lambda: self.start_match(self.config)).pack(side="left")
        self.button(actions, "New setup", lambda: self.show_setup(self.config.num_players), kind="secondary").pack(side="left", padx=12)
        self.button(actions, "Review final table", self.build_game, kind="secondary").pack(side="left")
        seed_note = "A fixed seed restarts the same dice sequence on replay." if self.config.seed is not None else "No seed selected: each new match uses a fresh dice sequence."
        self.label(self.body, seed_note, 9, fg=MUTED).pack(anchor="w", pady=(18, 0))

    def show_rules(self):
        if self.rules_window is not None and self.rules_window.winfo_exists():
            self.rules_window.lift()
            return
        window = tk.Toplevel(self.root)
        self.rules_window = window
        window.title("How to play Hog")
        window.geometry("660x670")
        window.minsize(640, 640)
        window.configure(bg=BG)
        window.transient(self.root)
        inner = tk.Frame(window, bg=BG)
        inner.pack(fill="both", expand=True, padx=30, pady=26)
        self.label(inner, "KNOW THE RULES", 9, fg=MINT).pack(anchor="w")
        self.label(inner, "Three rules. One goal.", 25, bold=True).pack(anchor="w", pady=(10, 18))
        sections = [
            ("01 / Race to 100", "Player 0 starts. Take turns choosing 0-10 dice. Be first to end a turn with at least 100 points, after all bonuses."),
            ("02 / Sow Sad", "Any rolled 1 makes your turn worth only 1 point. Otherwise, earn the sum of all dice. All chosen dice are rolled."),
            ("03 / Boar Brawl", "Choose 0 dice to gain max(1, 3 x abs(opponent tens digit - your ones digit)). Your score 21 vs 46 earns 9 points."),
            ("04 / Sus Fuss", "After adding turn points, a total with exactly 3 or 4 positive factors increases to the next larger prime. A total of 21 becomes 23. This also applies after choosing 0 dice."),
        ]
        for title, description in sections:
            self.label(inner, title, 12, bold=True, fg=GOLD).pack(anchor="w", pady=(5, 5))
            self.label(inner, description, 11, fg=MUTED, wraplength=585).pack(anchor="w", pady=(0, 15))
        self.button(inner, "Got it", window.destroy).pack(anchor="w", pady=(6, 0))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Hog Graphical Desktop Edition")
    parser.add_argument("--version", action="version", version=VERSION)
    parser.parse_args(argv)
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
    HogApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
