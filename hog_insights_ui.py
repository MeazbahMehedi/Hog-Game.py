"""Statistics and replay windows, composed with the desktop application.

Only the Tk thread renders these views. All figures come from recorded turns.
"""

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    tk = None

from hog_drawing import draw_die
from hog_charts import draw_dice_choices, draw_scores, score_position
from hog_statistics import read_matches, summarize, key_moments, explain_turn

PLAYBACK_DELAYS = {'0.5×': 1600, '1×': 800, '2×': 400, '4×': 200}


class InsightsUI:
    def _insight_window(self, title):
        panel = self.analysis_shell(title)
        self.analysis_window.geometry('1020x800')
        self.analysis_window.minsize(900, 720)
        return panel

    def show_statistics(self, initial_profile=None):
        panel = self._insight_window('Statistics / your recorded games')
        controls = tk.Frame(panel, bg=self.palette.bg)
        controls.pack(fill='x', pady=(0, 14))
        self.label(controls, 'View', 10, fg=self.palette.muted).pack(side='left', padx=(0, 10))
        choices = {'All recorded seats': None}
        for profile in self.store.profiles():
            choices['Profile / ' + profile['name']] = profile['id']
        selected = next((label for label, identifier in choices.items() if identifier == initial_profile), None)
        if initial_profile is None and len(choices) > 1:
            most_active = max(self.store.stats(), key=lambda row: row['played'])['id']
            selected = next(label for label, identifier in choices.items() if identifier == most_active)
        self.statistics_profile = tk.StringVar(self.root, selected or 'All recorded seats')
        combo = ttk.Combobox(controls, textvariable=self.statistics_profile, values=tuple(choices),
                             state='readonly', style='Hog.TCombobox', width=33)
        combo.pack(side='left')
        self.button(controls, 'Replays', self.show_replay, kind='secondary').pack(side='right')
        self.statistics_status = self.label(panel, '', 9, fg=self.palette.muted, wraplength=930)
        self.statistics_status.pack(fill='x', pady=(0, 12))
        cards = tk.Frame(panel, bg=self.palette.bg)
        cards.pack(fill='x', pady=(0, 14))
        values = []
        for column, title in enumerate(('MATCHES', 'RECORDED WINS', 'WIN RATE', 'MEAN GAIN / TURN')):
            cards.columnconfigure(column, weight=1, uniform='statistics')
            card = self.panel(cards)
            card.grid(row=0, column=column, sticky='ew', padx=(0 if column == 0 else 4, 0 if column == 3 else 4))
            self.label(card, title, 8, fg=self.palette.muted).pack(anchor='w', padx=14, pady=(10, 4))
            value = self.label(card, '—', 24, bold=True)
            value.pack(anchor='w', padx=14, pady=(0, 10))
            values.append(value)
        notebook = ttk.Notebook(panel, style='Hog.TNotebook')
        notebook.pack(fill='both', expand=True)
        self.statistics_tabs = {}
        for title in ('Dice choices', 'Opponents', 'Records'):
            page = tk.Frame(notebook, bg=self.palette.panel)
            notebook.add(page, text=title)
            self.statistics_tabs[title] = page
        page = self.statistics_tabs['Dice choices']
        self.statistics_chart = tk.Canvas(page, bg=self.palette.panel, height=280, highlightthickness=0)
        self.statistics_chart.pack(fill='both', expand=True, padx=12, pady=12)
        self.statistics_rule_counts = self.label(page, '', 10, fg=self.palette.muted, wraplength=890)
        self.statistics_rule_counts.pack(anchor='w', padx=20, pady=(0, 16))
        page = self.statistics_tabs['Opponents']
        self.label(page, 'Recorded results against each opponent; small samples are descriptive.',
                   10, fg=self.palette.muted).pack(anchor='w', padx=18, pady=16)
        listing = tk.Frame(page, bg=self.palette.panel)
        listing.pack(fill='both', expand=True, padx=16, pady=(0, 16))
        tree = self.statistics_opponents = ttk.Treeview(listing, columns=('opponent', 'played', 'wins', 'losses', 'rate'),
                                                       show='headings', style='Hog.Treeview')
        for name, label, width in (('opponent', 'Opponent', 370), ('played', 'Played', 100),
                                    ('wins', 'Wins', 90), ('losses', 'Losses', 90), ('rate', 'Win rate', 110)):
            tree.heading(name, text=label)
            tree.column(name, width=width, minwidth=70, anchor='w' if name == 'opponent' else 'center')
        scrollbar = ttk.Scrollbar(listing, orient='vertical', command=tree.yview)
        scrollbar.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(fill='both', expand=True)
        page = self.statistics_tabs['Records']
        record_values = []
        for title in ('Highest final score', 'Largest single-turn gain', 'Largest Sus Fuss bonus',
                      'Largest winning margin', 'Longest winning streak'):
            row = tk.Frame(page, bg=self.palette.raised)
            row.pack(fill='x', padx=20, pady=(10, 0))
            self.label(row, title, 12, bold=True).pack(side='left', padx=16, pady=10)
            value = self.label(row, '—', 19, bold=True, fg=self.palette.accent)
            value.pack(side='right', padx=16, pady=10)
            record_values.append(value)
        self.records_text = self.label(page, '', 10, fg=self.palette.muted, wraplength=850)
        self.records_text.pack(anchor='w', padx=24, pady=16)
        self.label(panel, 'Snapshot at opening; reopen to refresh. Standard completed desktop matches only. Practice, terminal games and tournaments are separate.',
                   9, fg=self.palette.muted, wraplength=930).pack(anchor='w', pady=(12, 0))
        self.statistics_matches, self.statistics_skipped = read_matches(self.store.history())

        def redraw(_event=None):
            if self.analysis_window is None:
                return
            draw_dice_choices(self.statistics_chart, self.statistics_summary['dice_counts'], self.palette, self.family)
            self._style_insight_table()

        def refresh(_event=None):
            identifier = choices[self.statistics_profile.get()]
            data = self.statistics_summary = summarize(self.statistics_matches, identifier)
            rate = '—' if data['win_rate'] is None else f"{data['win_rate']:.1%}"
            gain = '—' if data['average_gain'] is None else f"{data['average_gain']:.2f}"
            for label, value in zip(values, (str(data['matches']), str(data['wins']), rate, gain)):
                label.configure(text=value)
            scope = ('Both seats included: every match contributes two appearances and one win. '
                     'The overall 50% is not a player skill estimate.' if identifier is None else
                     'Profile identity filter; guest games and other profiles are excluded.')
            skipped = f' {self.statistics_skipped} unreadable/inconsistent record(s) excluded.' if self.statistics_skipped else ''
            self.statistics_status.configure(text=f"{data['appearances']} recorded seat appearances. {scope}{skipped}")
            if data['turns']:
                rules = f"{data['turns']} turns / {data['zeros']} zero-dice turns / {data['sow']} Sow Sad turns / {data['bonuses']} Sus Fuss bonuses"
            else:
                rules = 'No completed matches for this selection. Assign a profile to a human seat before playing to track personal records.'
            self.statistics_rule_counts.configure(text=rules)
            for item in tree.get_children():
                tree.delete(item)
            for row in data['opponents']:
                tree.insert('', 'end', values=(row['name'], row['played'], row['wins'], row['played'] - row['wins'],
                                               f"{row['wins'] / row['played']:.1%}"))
            if data['appearances']:
                streak = str(data['best_streak']) if identifier is not None else 'Select one profile'
                for label, value in zip(record_values, (data['best_score'], data['best_gain'], data['best_bonus'], data['best_margin'], streak)):
                    label.configure(text=str(value))
                self.records_text.configure(text='Turn gain includes Sus Fuss. Streaks follow completed-match order.\nRecords describe this selected history; they are not optimal-play ratings.')
            else:
                for label in record_values:
                    label.configure(text='—')
                self.records_text.configure(text='No personal records yet. Complete a standard profile match to begin.')
            redraw()
        self.statistics_refresh = refresh
        self._redraw_insights = redraw
        combo.bind('<<ComboboxSelected>>', refresh)
        self.statistics_chart.bind('<Configure>', redraw)
        refresh()

    def _style_insight_table(self):
        style = ttk.Style(self.root)
        style.configure('Hog.TNotebook', background=self.palette.panel, borderwidth=0)
        style.configure('Hog.TNotebook.Tab', background=self.palette.raised, foreground=self.palette.text, padding=(16, 8))
        style.map('Hog.TNotebook.Tab', background=[('selected', self.palette.accent), ('active', self.palette.border)],
                  foreground=[('selected', self.palette.accent_text)])
        style.configure('Hog.Treeview', background=self.palette.panel, fieldbackground=self.palette.panel,
                        foreground=self.palette.text, rowheight=30, font=(self.family, 10), borderwidth=0)
        style.configure('Hog.Treeview.Heading', background=self.palette.raised, foreground=self.palette.text,
                        font=(self.family, 10, 'bold'), padding=8)
        style.map('Hog.Treeview', background=[('selected', self.palette.accent)],
                  foreground=[('selected', self.palette.accent_text)])
        style.map('Hog.Treeview.Heading', background=[('active', self.palette.border)])

    def show_replay(self, match_id=None):
        panel = self._insight_window('Match replay / timeline')
        matches, skipped = read_matches(self.store.history()[:100])
        self.replay_playing = False
        self.replay_states = ()
        self.replay_index = 0
        if not matches:
            message = 'Complete a standard desktop match to create a replay.'
            if skipped:
                message += f' {skipped} unreadable/inconsistent record(s) excluded.'
            self.label(panel, message, 12, wraplength=900).pack(anchor='w')
            return
        labels = [f"{match.finished_at} / {' vs '.join(match.config.names)} / {match.identifier[:6]}" for match in matches]
        chosen = next((i for i, match in enumerate(matches) if match.identifier == match_id), 0)
        self.replay_selection = tk.StringVar(self.root, labels[chosen])
        combo = ttk.Combobox(panel, textvariable=self.replay_selection, values=labels,
                             state='readonly', style='Hog.TCombobox')
        combo.pack(fill='x', pady=(0, 10))
        self.replay_heading = self.label(panel, '', 19, bold=True)
        self.replay_heading.pack(anchor='w', pady=(0, 8))
        chart = self.replay_chart = tk.Canvas(panel, height=210, bg=self.palette.panel, highlightthickness=0)
        chart.pack(fill='both', expand=True)
        self.replay_timeline_var = tk.DoubleVar(self.root, 0)
        timeline = self.replay_timeline = tk.Scale(panel, from_=0, to=1, orient='horizontal', resolution=1,
                                                  variable=self.replay_timeline_var, showvalue=False,
                                                  bg=self.palette.bg, fg=self.palette.text,
                                                  troughcolor=self.palette.raised, highlightthickness=0,
                                                  activebackground=self.palette.accent, sliderlength=22)
        timeline.pack(fill='x', pady=(6, 0))
        self.replay_step_label = self.label(panel, '', 9, fg=self.palette.muted)
        self.replay_step_label.pack(anchor='w')
        dice = self.replay_dice_canvas = tk.Canvas(panel, height=76, bg=self.palette.panel, highlightthickness=0)
        dice.pack(fill='x', pady=(8, 0))
        self.replay_details = self.label(panel, '', 10, wraplength=920, fg=self.palette.accent, height=3)
        self.replay_details.pack(fill='x', pady=8)
        actions = tk.Frame(panel, bg=self.palette.bg)
        actions.pack(fill='x', pady=4)
        self.replay_buttons = {}
        for text, command in (('First', lambda: self.replay_advance(-999)), ('Previous', lambda: self.replay_advance(-1)),
                              ('Play', lambda: self.replay_play_pause()), ('Next', lambda: self.replay_advance(1)),
                              ('Last', lambda: self.replay_advance(999))):
            button = self.button(actions, text, command, kind='secondary')
            button.configure(padx=13, pady=8)
            button.pack(side='left', padx=(0, 6))
            self.replay_buttons[text] = button
        self.replay_speed = tk.StringVar(self.root, '1×')
        speed = ttk.Combobox(actions, textvariable=self.replay_speed, values=tuple(PLAYBACK_DELAYS),
                             width=5, state='readonly', style='Hog.TCombobox')
        speed.pack(side='right')
        self.label(actions, 'Speed', 9, fg=self.palette.muted).pack(side='right', padx=8)
        moments_row = tk.Frame(panel, bg=self.palette.bg)
        moments_row.pack(fill='x', pady=(8, 0))
        self.label(moments_row, 'Key turn', 9, fg=self.palette.muted).pack(side='left', padx=(0, 10))
        self.replay_moment = tk.StringVar(self.root)
        moments_box = ttk.Combobox(moments_row, textvariable=self.replay_moment, state='readonly',
                                   style='Hog.TCombobox', width=62)
        moments_box.pack(side='left', fill='x', expand=True)
        self.label(panel, 'Click the chart or drag the timeline. Key turns are factual milestones, not AI move evaluations.' +
                   (f' {skipped} invalid record(s) excluded.' if skipped else ''),
                   9, fg=self.palette.muted, wraplength=930).pack(anchor='w', pady=(10, 0))
        self._replay_drawing = False

        def stop():
            self.replay_playing = False
            if self.analysis_pending is not None:
                self.root.after_cancel(self.analysis_pending)
                self.analysis_pending = None
            self.replay_buttons['Play'].configure(text='Play')

        def draw(_event=None):
            if not self.replay_states or self.analysis_window is None:
                return
            state = self.replay_states[self.replay_index]
            names = self.replay_record['config']['names']
            self.replay_heading.configure(text=f"{names[0]} {state['scores'][0]} : {state['scores'][1]} {names[1]}")
            draw_scores(chart, self.replay_states, names, self.palette, self.family, self.replay_index, self.replay_moments)
            dice.delete('all')
            event = state['event']
            if event:
                for index, value in enumerate(event.outcomes):
                    draw_die(dice, 18 + index * 64, 10, 48, value, accent=value == 1, palette=self.palette)
                if not event.outcomes:
                    dice.create_text(18, 35, text='0 DICE / BOAR BRAWL', anchor='w', fill=self.palette.text,
                                     font=(self.family, 12, 'bold'))
            else:
                dice.create_text(18, 35, text='THE STARTING TABLE', anchor='w', fill=self.palette.muted,
                                 font=(self.family, 12))
            self.replay_details.configure(text=explain_turn(state, names))
            self.replay_step_label.configure(text=f'Position {self.replay_index} of {len(self.replay_states) - 1} / recorded turns')
            self.replay_moment.set(next((label for label, number in self.replay_moment_labels.items() if number == self.replay_index), 'Choose a milestone'))
            self._replay_drawing = True
            self.replay_timeline_var.set(self.replay_index)
            self._replay_drawing = False
            last = self.replay_index == len(self.replay_states) - 1
            for label in ('Next', 'Last'):
                self.replay_buttons[label].configure(state='disabled' if last else 'normal')
            for label in ('First', 'Previous'):
                self.replay_buttons[label].configure(state='disabled' if self.replay_index == 0 else 'normal')

        def seek(index):
            if self._replay_drawing or not self.replay_states:
                return
            position = max(0, min(len(self.replay_states) - 1, int(float(index))))
            if position == self.replay_index:
                return
            stop()
            self.replay_index = position
            draw()

        def advance(delta):
            seek(self.replay_index + delta)

        def tick():
            self.analysis_pending = None
            if not self.replay_playing or self.analysis_window is None:
                return
            self.replay_index += 1
            draw()
            if self.replay_index >= len(self.replay_states) - 1:
                stop()
            else:
                self.analysis_pending = self.root.after(PLAYBACK_DELAYS[self.replay_speed.get()], tick)

        def play_pause():
            if self.replay_playing:
                stop()
                return
            if self.replay_index == len(self.replay_states) - 1:
                self.replay_index = 0
                draw()
            self.replay_playing = True
            self.replay_buttons['Play'].configure(text='Pause')
            self.analysis_pending = self.root.after(PLAYBACK_DELAYS[self.replay_speed.get()], tick)

        def change_speed(_event=None):
            if self.replay_playing:
                if self.analysis_pending is not None:
                    self.root.after_cancel(self.analysis_pending)
                self.analysis_pending = self.root.after(PLAYBACK_DELAYS[self.replay_speed.get()], tick)

        def load(_event=None):
            stop()
            match = matches[labels.index(self.replay_selection.get())]
            self.replay_record = match.record
            self.replay_states = match.states
            self.replay_index = 0
            self.replay_moments = key_moments(match.states)
            self.replay_moment_labels = {f'Turn {number:02d} / {title}': number for number, title in self.replay_moments}
            moments_box.configure(values=tuple(self.replay_moment_labels))
            self.replay_moment.set(next(iter(self.replay_moment_labels), ''))
            timeline.configure(to=len(match.states) - 1)
            draw()
        self.replay_seek, self.replay_advance = seek, advance
        self.replay_play_pause, self.replay_tick = play_pause, tick
        self.replay_change_speed, self.replay_load = change_speed, load
        self._redraw_insights = draw
        chart.bind('<Configure>', draw)
        chart.bind('<Button-1>', lambda event: seek(score_position(chart, len(self.replay_states) - 1, event.x)))
        timeline.configure(command=seek)
        timeline.bind("<ButtonPress-1>", lambda _event: stop())
        combo.bind('<<ComboboxSelected>>', load)
        speed.bind('<<ComboboxSelected>>', change_speed)
        moments_box.bind('<<ComboboxSelected>>', lambda _event: seek(self.replay_moment_labels[self.replay_moment.get()]))
        load()
