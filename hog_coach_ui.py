"""Learning windows for live advice, decision review, and model-based puzzles."""

try:
    import tkinter as tk
    from tkinter import ttk
except ImportError:
    tk = None

from hog_ai import advice_text
from hog_coach import (ASSUMPTIONS, TIE_TOLERANCE, coach_position, explain_choice,
                       review_match, puzzles, check_answer)
from hog_statistics import read_matches


class CoachUI:
    def _coach_text(self, parent):
        frame = tk.Frame(parent, bg=self.palette.panel)
        frame.pack(fill='both', expand=True, padx=12, pady=12)
        scroll = ttk.Scrollbar(frame)
        scroll.pack(side='right', fill='y')
        text = tk.Text(frame, bg=self.palette.panel, fg=self.palette.text, relief='flat', wrap='word',
                       padx=12, pady=10, spacing3=6, font=(self.family, 11), yscrollcommand=scroll.set,
                       insertbackground=self.palette.text, state='disabled', height=8)
        text.pack(fill='both', expand=True)
        scroll.configure(command=text.yview)
        return text

    @staticmethod
    def _set_coach_text(widget, text):
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', text)
        widget.configure(state='disabled')
        widget.yview_moveto(0)

    def show_coaching_hub(self):
        panel = self._insight_window('Coach / learn from each decision')
        self.label(panel, 'OFFLINE ANALYSIS / STANDARD RULES', 9, bold=True, fg=self.palette.accent).pack(anchor='w', pady=(0, 14))
        self.label(panel, 'Choose with a reason.', 30, bold=True).pack(anchor='w')
        self.label(panel, 'Study a position, revisit your decisions, or solve a challenge.',
                   12, fg=self.palette.muted).pack(anchor='w', pady=(10, 24))
        for number, title, text, command in (
            ('01', 'Live move coach', f'During a human turn, use Coach / {self.preferences.shortcuts[3]}. Compare every dice count and read the model explanation.',
             lambda: self.show_setup(1)),
            ('02', 'Decision review', 'Review a completed match using the positions before its rolls. Separate decision gaps from dice luck.',
             self.show_review),
            ('03', 'Puzzle challenges', 'Solve eight standard-rule positions. Any numerically tied model-best move is accepted.',
             self.show_puzzles)):
            card = self.panel(panel)
            card.pack(fill='x', pady=(0, 12))
            inside = tk.Frame(card, bg=self.palette.panel)
            inside.pack(fill='x', padx=20, pady=16)
            self.label(inside, number + ' / ' + title, 16, bold=True).pack(anchor='w')
            self.label(inside, text, 10, fg=self.palette.muted, wraplength=720).pack(anchor='w', pady=(7, 12))
            def open_view(action=command):
                self.close_analysis()
                action()
            self.button(inside, 'Set up a match' if number == '01' else 'Open', open_view, kind='secondary').pack(anchor='w')
        self.label(panel, ASSUMPTIONS, 9, fg=self.palette.muted, wraplength=930).pack(anchor='w', pady=(8, 0))

    def show_coach(self):
        if (self.screen != 'game' or self.session.finished or self.animating or self.paused
                or not self.config.is_human(self.session.current_player)):
            return
        who = self.session.current_player
        own, other = self.session.scores[who], self.session.scores[1 - who]
        turn, name, choice = self.session.turn_number, self.config.names[who], self.selected_count
        panel = self._insight_window('Move coach / compare your choices')
        self.label(panel, f'{name} / turn {turn} / snapshot {own} vs {other}', 11,
                   fg=self.palette.muted).pack(anchor='w')
        self.analysis_status = self.label(panel, 'Calculating exact fair-dice values...', 10,
                                           fg=self.palette.accent, wraplength=930)
        self.analysis_status.pack(fill='x', pady=(12, 14))
        notebook = ttk.Notebook(panel, style='Hog.TNotebook')
        notebook.pack(fill='both', expand=True)
        moves_page = tk.Frame(notebook, bg=self.palette.panel)
        explanation_page = tk.Frame(notebook, bg=self.palette.panel)
        notebook.add(moves_page, text='Move comparison')
        notebook.add(explanation_page, text='Explanation')
        self.coach_explanation = self._coach_text(explanation_page)
        move_listing = tk.Frame(moves_page, bg=self.palette.panel)
        move_listing.pack(fill='both', expand=True, padx=14, pady=14)
        self.coach_table = ttk.Treeview(move_listing, columns=('dice', 'gain', 'win', 'risk', 'finish'),
                                        show='headings', height=11, style='Hog.Treeview', selectmode='browse')
        for key, label, width in (('dice', 'Dice (* model-best)', 160), ('gain', 'Expected gain', 145),
                                  ('win', 'Model win chance', 170), ('risk', 'Sow Sad risk', 145),
                                  ('finish', 'Finish this turn', 160)):
            self.coach_table.heading(key, text=label)
            self.coach_table.column(key, width=width, minwidth=90, anchor='center')
        move_scroll = ttk.Scrollbar(move_listing, orient='vertical', command=self.coach_table.yview)
        move_scroll.pack(side='right', fill='y')
        self.coach_table.configure(yscrollcommand=move_scroll.set)
        self.coach_table.pack(fill='both', expand=True)
        self.coach_choice_status = self.label(moves_page, 'Select a row to compare a move, then open Explanation.',
                                             10, fg=self.palette.muted, wraplength=890)
        self.coach_choice_status.pack(anchor='w', padx=18, pady=(0, 12))
        self.button(panel, 'Read selected move explanation', lambda: notebook.select(explanation_page),
                    kind='secondary').pack(anchor='w', pady=12)
        self.label(panel, 'Snapshot only; reopen for a new position. Advice never chooses or plays your move.\n' + ASSUMPTIONS,
                   9, fg=self.palette.muted, wraplength=930).pack(anchor='w')
        self.coach_report = None
        self.coach_chosen = choice

        def choose(_event=None):
            if self.coach_report is None:
                return
            selected = self.coach_table.selection()
            if selected:
                self.coach_chosen = int(selected[0])
            report = self.coach_report
            row = report.moves[self.coach_chosen]
            best = report.moves[report.recommended]
            self.coach_choice_status.configure(text=f'Considering {self.coach_chosen} dice / model gap {max(0, best.win_probability - row.win_probability) * 100:.2f} percentage points. Read Explanation for the reasoning.')
            self._set_coach_text(self.coach_explanation, explain_choice(report, self.coach_chosen))

        def redraw():
            self._style_insight_table()
            if self.coach_report:
                self.coach_table.tag_configure('best', foreground=self.palette.accent)
        self._redraw_insights = redraw
        self.coach_table.bind('<<TreeviewSelect>>', choose)

        def ready(report):
            self.coach_report = report
            self.analysis_status.configure(text=advice_text(own, other, report.moves))
            for row in report.moves:
                best = row.dice in report.best_choices
                self.coach_table.insert('', 'end', iid=str(row.dice), tags=('best',) if best else (),
                    values=(f'{row.dice}' + (' *' if best else ''), f'{row.expected_gain:.2f}',
                            f'{row.win_probability:.2%}', f'{row.sow_sad_probability:.1%}',
                            f'{report.finish_chances[row.dice]:.2%}'))
            self.coach_table.selection_set(str(choice))
            self.coach_table.see(str(choice))
            choose()
            redraw()
        redraw()
        self.poll_analysis(self.worker.submit(coach_position, own, other), ready)

    def show_review(self, match_id=None):
        panel = self._insight_window('Decision review / before the roll')
        matches, skipped = read_matches(self.store.history()[:100])
        actions = tk.Frame(panel, bg=self.palette.bg)
        actions.pack(fill='x', pady=(0, 10))
        self.button(actions, 'Puzzle challenges', self.show_puzzles, kind='secondary').pack(side='right')
        if not matches:
            text = 'Complete a standard desktop match to review its decisions.'
            if skipped:
                text += f' {skipped} invalid record(s) excluded.'
            self.label(panel, text, 12, wraplength=900).pack(anchor='w')
            return
        labels = [f"{index + 1:02d} / {match.finished_at} / {' vs '.join(match.config.names)} / {match.identifier[:6]}" for index, match in enumerate(matches)]
        self.review_labels = tuple(labels)
        index = next((i for i, match in enumerate(matches) if match.identifier == match_id), 0)
        self.review_match_var = tk.StringVar(self.root, labels[index])
        combo = ttk.Combobox(actions, textvariable=self.review_match_var, values=labels,
                             state='readonly', style='Hog.TCombobox')
        combo.pack(side='left', fill='x', expand=True, padx=(0, 12))
        filters = tk.Frame(panel, bg=self.palette.bg)
        filters.pack(fill='x')
        self.label(filters, 'Seat', 9, fg=self.palette.muted).pack(side='left', padx=(0, 8))
        self.review_seat = tk.StringVar(self.root, 'All seats')
        seat_box = ttk.Combobox(filters, textvariable=self.review_seat, state='readonly', style='Hog.TCombobox', width=26)
        seat_box.pack(side='left')
        self.review_order = tk.StringVar(self.root, 'Largest model gap')
        order = ttk.Combobox(filters, textvariable=self.review_order, values=('Largest model gap', 'Turn order'),
                             state='readonly', style='Hog.TCombobox', width=23)
        order.pack(side='left', padx=12)
        self.analysis_status = self.label(panel, '', 10, fg=self.palette.accent, wraplength=930)
        self.analysis_status.pack(fill='x', pady=(12, 10))
        notebook = ttk.Notebook(panel, style='Hog.TNotebook')
        notebook.pack(fill='both', expand=True)
        turns_page, explanation_page = (tk.Frame(notebook, bg=self.palette.panel) for _ in range(2))
        notebook.add(turns_page, text='Decisions')
        notebook.add(explanation_page, text='Selected decision')
        self.review_explanation = self._coach_text(explanation_page)
        listing = tk.Frame(turns_page, bg=self.palette.panel)
        listing.pack(fill='both', expand=True, padx=12, pady=12)
        tree = self.review_table = ttk.Treeview(listing, columns=('turn', 'player', 'position', 'chosen', 'best', 'gap', 'assessment'),
                                               show='headings', style='Hog.Treeview', selectmode='browse')
        for key, title, width in (('turn', 'Turn', 55), ('player', 'Player', 165), ('position', 'Before', 100),
                                  ('chosen', 'Played', 75), ('best', 'Best dice', 125), ('gap', 'Gap (pp)', 100),
                                  ('assessment', 'Assessment', 130)):
            tree.heading(key, text=title)
            tree.column(key, width=width, minwidth=45, anchor='w' if key == 'player' else 'center')
        scroll = ttk.Scrollbar(listing, orient='vertical', command=tree.yview)
        scroll.pack(side='right', fill='y')
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(fill='both', expand=True)
        self.review_selected_status = self.label(turns_page, '', 10, fg=self.palette.muted, wraplength=890)
        self.review_selected_status.pack(anchor='w', padx=18, pady=(0, 12))
        self.button(panel, 'Explain selected decision', lambda: notebook.select(explanation_page),
                    kind='secondary').pack(anchor='w', pady=10)
        self.label(panel, 'Gap = best model win chance minus played move value, in percentage points.\n'
                   'Labels: Model-best (tied), Close (≤1 pp), Review (≤5 pp), Large gap (>5 pp). These are learning thresholds.\n' + ASSUMPTIONS,
                   9, fg=self.palette.muted, wraplength=930).pack(anchor='w')
        self.review_rows = ()
        self.review_filtered = ()
        self.review_record = None

        def select(_event=None):
            if not tree.selection() or self.review_record is None:
                return
            row = self.review_rows[int(tree.selection()[0])]
            event = row.event
            names = self.review_record['config']['names']
            self.review_selected_status.configure(text=f'Turn {event.number} / {names[event.player]} / played {event.num_rolls} dice / {row.assessment}. Open Selected decision for details.')
            outcomes = ', '.join(map(str, event.outcomes)) or 'zero dice'
            actual = (f'RECORDED OUTCOME (separate from the pre-roll evaluation)\n'
                      f'Dice: {outcomes}. Base gain {event.turn_points}; Sus Fuss +{event.bonus}; final score {event.score_after}.\n'
                      'A lucky or unlucky result does not change the move values calculated before the roll.\n\n')
            self._set_coach_text(self.review_explanation, actual + explain_choice(row.position, event.num_rolls))

        def refresh(_event=None):
            if self.review_record is None:
                return
            seat = None if self.review_seat.get() == 'All seats' else int(self.review_seat.get()[0])
            indexed = [(i, row) for i, row in enumerate(self.review_rows) if seat is None or row.event.player == seat]
            if self.review_order.get() == 'Largest model gap':
                indexed.sort(key=lambda item: (-item[1].gap, item[1].event.number))
            self.review_filtered = tuple(row for _, row in indexed)
            for item in tree.get_children():
                tree.delete(item)
            names = self.review_record['config']['names']
            for i, row in indexed:
                event, report = row.event, row.position
                best = ','.join(map(str, report.best_choices))
                if len(best) > 16:
                    best = f'{report.recommended} + ties'
                tree.insert('', 'end', iid=str(i), values=(event.number, names[event.player],
                    f'{event.score_before}:{event.opponent_score}', event.num_rolls, best,
                    f'{row.gap * 100:.2f}', row.assessment))
            best_count = sum(row.gap <= TIE_TOLERANCE for _, row in indexed)
            mean = sum(row.gap for _, row in indexed) / len(indexed) if indexed else 0
            self.analysis_status.configure(text=f'{len(indexed)} decisions / {best_count} model-best / mean gap {mean * 100:.2f} pp. '
                'The mean is a decision metric, not a match-loss probability.' + (f' {skipped} invalid record(s) excluded.' if skipped else ''))
            children = tree.get_children()
            if children:
                tree.selection_set(children[0])
                select()

        def load(_event=None):
            if self.analysis_pending is not None:
                self.root.after_cancel(self.analysis_pending)
                self.analysis_pending = None
            match = matches[labels.index(self.review_match_var.get())]
            self.review_rows, self.review_filtered, self.review_record = (), (), None
            for item in tree.get_children():
                tree.delete(item)
            self._set_coach_text(self.review_explanation, 'Calculating pre-roll values...')
            self.analysis_status.configure(text='Calculating decision values...')
            self.review_selected_status.configure(text='')
            seat_labels = ('All seats', f'0 / {match.config.names[0]}', f'1 / {match.config.names[1]}')
            seat_box.configure(values=seat_labels)
            default = next((seat_labels[seat + 1] for seat in (0, 1) if match.config.is_human(seat)), seat_labels[0])
            self.review_seat.set(default)
            def ready(rows):
                self.review_rows, self.review_record = rows, match.record
                refresh()
            self.poll_analysis(self.worker.submit(review_match, match.record), ready)
        self.review_refresh, self.review_load = refresh, load
        self._redraw_insights = self._style_insight_table
        self._style_insight_table()
        tree.bind('<<TreeviewSelect>>', select)
        seat_box.bind('<<ComboboxSelected>>', refresh)
        order.bind('<<ComboboxSelected>>', refresh)
        combo.bind('<<ComboboxSelected>>', load)
        load()

    def show_puzzles(self):
        panel = self._insight_window('Puzzle challenges / find a model-best move')
        if not hasattr(self, 'puzzle_progress'):
            self.puzzle_progress = {}
        catalog = puzzles()
        labels = [f'{index + 1:02d} / {puzzle.title}' for index, puzzle in enumerate(catalog)]
        self.puzzle_selection = tk.StringVar(self.root, labels[0])
        combo = ttk.Combobox(panel, textvariable=self.puzzle_selection, values=labels,
                             state='readonly', style='Hog.TCombobox')
        combo.pack(fill='x', pady=(0, 12))
        self.puzzle_score = self.label(panel, '', 28, bold=True)
        self.puzzle_score.pack(anchor='w')
        self.puzzle_prompt = self.label(panel, '', 11, fg=self.palette.muted, wraplength=930)
        self.puzzle_prompt.pack(anchor='w', pady=(8, 14))
        self.puzzle_count = 5
        selector = tk.Frame(panel, bg=self.palette.bg)
        selector.pack(fill='x')
        self.puzzle_buttons = []

        def choose(count):
            self.puzzle_count = count
            redraw()
        for count in range(11):
            selector.columnconfigure(count, weight=1, uniform='puzzle-dice')
            button = self.button(selector, str(count), lambda value=count: choose(value), kind='secondary')
            button.configure(padx=0)
            button.grid(row=0, column=count, sticky='ew', padx=2)
            self.puzzle_buttons.append(button)
        actions = tk.Frame(panel, bg=self.palette.bg)
        actions.pack(fill='x', pady=12)
        self.puzzle_submit = self.button(actions, 'Check my move', lambda: submit())
        self.puzzle_submit.pack(side='left')
        self.puzzle_reveal = self.button(actions, 'Reveal explanation', lambda: reveal(), kind='secondary')
        self.puzzle_reveal.pack(side='left', padx=10)
        self.puzzle_next = self.button(actions, 'Next puzzle', lambda: next_puzzle(), kind='secondary')
        self.puzzle_next.pack(side='right')
        self.analysis_status = self.label(panel, '', 10, fg=self.palette.accent, wraplength=930, height=2)
        self.analysis_status.pack(fill='x', pady=(0, 4))
        self.puzzle_progress_label = self.label(panel, '', 9, fg=self.palette.muted)
        self.puzzle_progress_label.pack(anchor='w', pady=(0, 10))
        explanation_panel = self.panel(panel)
        explanation_panel.pack(fill='both', expand=True)
        self.puzzle_explanation = self._coach_text(explanation_panel)
        self.label(panel, 'No match is played. Progress lasts until the app closes; puzzle attempts never alter profile statistics.\n'
                   'Any model-best tie is accepted. Revealed answers do not count as unassisted solves.\n' + ASSUMPTIONS,
                   9, fg=self.palette.muted, wraplength=930).pack(anchor='w', pady=(12, 0))
        self.puzzle_report = None
        self.puzzle_ready = False

        def redraw():
            for count, button in enumerate(self.puzzle_buttons):
                active = count == self.puzzle_count
                fill = self.palette.accent if active else self.palette.raised
                button.configure(bg=fill, fg=self.palette.accent_text if active else self.palette.text,
                                 highlightbackground=fill, state='normal' if self.puzzle_ready else 'disabled')
            solved = sum(state['solved'] for state in self.puzzle_progress.values())
            state = self.puzzle_progress[self.current_puzzle.identifier]
            status = 'Solved unassisted' if state['solved'] else 'Answer revealed' if state['revealed'] else 'Not solved'
            self.puzzle_progress_label.configure(text=f'{solved}/{len(catalog)} solved unassisted this app session / {state["attempts"]} attempts on this puzzle / {status}')

        def submit():
            if not self.puzzle_ready:
                return
            correct, report = check_answer(self.current_puzzle, self.puzzle_count)
            state = self.puzzle_progress[self.current_puzzle.identifier]
            state['attempts'] += 1
            if correct:
                if not state['revealed']:
                    state['solved'] = True
                self.analysis_status.configure(text='Correct: this move is model-best.' + (' Answer was revealed earlier; this is an assisted solve.' if state['revealed'] else ''))
                self._set_coach_text(self.puzzle_explanation, explain_choice(report, self.puzzle_count))
            else:
                gap = report.moves[report.recommended].win_probability - report.moves[self.puzzle_count].win_probability
                self.analysis_status.configure(text=f'Try again. Your choice is {gap * 100:.2f} percentage points below the best model value. Check guaranteed points, immediate finish chances and risk.')
                self._set_coach_text(self.puzzle_explanation, 'Try another dice count, or reveal the full comparison. No new dice were rolled.')
            redraw()

        def reveal():
            if not self.puzzle_ready:
                return
            self.puzzle_progress[self.current_puzzle.identifier]['revealed'] = True
            self.analysis_status.configure(text='Explanation revealed. You can still explore choices; later answers are assisted.')
            self._set_coach_text(self.puzzle_explanation, explain_choice(self.puzzle_report, self.puzzle_count))
            redraw()

        def load(_event=None):
            if self.analysis_pending is not None:
                self.root.after_cancel(self.analysis_pending)
                self.analysis_pending = None
            self.current_puzzle = catalog[labels.index(self.puzzle_selection.get())]
            puzzle = self.current_puzzle
            self.puzzle_progress.setdefault(puzzle.identifier, {'attempts': 0, 'solved': False, 'revealed': False})
            self.puzzle_report, self.puzzle_ready, self.puzzle_count = None, False, 5
            self.puzzle_score.configure(text=f'You {puzzle.score} : {puzzle.opponent} Opponent')
            self.puzzle_prompt.configure(text=puzzle.prompt)
            self.analysis_status.configure(text='Calculating fair-dice model...')
            self.puzzle_submit.configure(state='disabled')
            self.puzzle_reveal.configure(state='disabled')
            self._set_coach_text(self.puzzle_explanation, 'Choose the dice count with the highest model chance of winning. This is a position puzzle, not a sampled roll.')
            redraw()
            def ready(report):
                self.puzzle_report, self.puzzle_ready = report, True
                self.puzzle_submit.configure(state='normal')
                self.puzzle_reveal.configure(state='normal')
                self.analysis_status.configure(text='Choose 0-10 dice, then check your move.')
                redraw()
            self.poll_analysis(self.worker.submit(coach_position, puzzle.score, puzzle.opponent), ready)

        def next_puzzle():
            index = (labels.index(self.puzzle_selection.get()) + 1) % len(labels)
            self.puzzle_selection.set(labels[index])
            load()
        self.puzzle_load = load
        self._redraw_insights = redraw
        combo.bind('<<ComboboxSelected>>', load)
        load()
