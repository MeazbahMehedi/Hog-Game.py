"""Profile campaign map, earned cosmetics, milestones and isolated stage tables."""

try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    tk = None
import sqlite3
from uuid import uuid4

from hog import GameSession, STRATEGIES, seeded_dice
from hog_campaign import (stages, stage_by_id, OBJECTIVES, available_stages,
                          cosmetics, earned_cosmetics, campaign_achievements,
                          objective_status, evaluate_stage)
from hog_drawing import draw_die, draw_avatar
from hog_preferences import PALETTES
from dataclasses import asdict


class CampaignUI:
    def profile_equipment(self, identifier=None):
        try:
            return self.store.equipment(identifier)
        except ValueError:
            return self.store.equipment(None)

    def seat_skin(self, seat):
        identifier = self.config.profile_ids[seat] if self.config is not None else None
        return self.profile_equipment(identifier)['dice']

    def refresh_profile_art(self):
        def redraw(widget):
            if hasattr(widget, '_hog_avatar'):
                name, player, size, identifier = widget._hog_avatar
                style = self.profile_equipment(identifier)['avatar']
                draw_avatar(widget, name, size, self.palette, player, style)
            for child in widget.winfo_children():
                redraw(child)
        redraw(self.root)
        if self.screen == 'game':
            self._draw_outcomes()

    def show_campaign(self, profile_id=None):
        panel = self._insight_window('Campaign / the road to the summit')
        self.analysis_window.geometry('1060x840')
        profiles = self.store.profiles()
        if profile_id is None:
            profile_id = getattr(self, 'campaign_profile_id', None)
        lookup = {row['name']: row['id'] for row in profiles}
        controls = tk.Frame(panel, bg=self.palette.bg)
        controls.pack(fill='x', pady=(0, 12))
        self.label(controls, 'Profile', 10, fg=self.palette.muted).pack(side='left', padx=(0, 8))
        chosen = next((row['name'] for row in profiles if row['id'] == profile_id), next(iter(lookup), ''))
        self.campaign_profile_var = tk.StringVar(self.root, chosen)
        combo = ttk.Combobox(controls, textvariable=self.campaign_profile_var, values=tuple(lookup),
                             state='readonly' if profiles else 'disabled', style='Hog.TCombobox', width=22)
        combo.pack(side='left')
        new_name = tk.StringVar(self.root)
        self.campaign_new_name = new_name
        self.button(controls, 'Create profile', lambda: create()).pack(side='right')
        entry = tk.Entry(controls, textvariable=new_name, width=20, bg=self.palette.panel,
                         fg=self.palette.text, insertbackground=self.palette.text, relief='flat')
        entry.pack(side='right', ipady=9, padx=10)
        self.label(controls, 'New name', 9, fg=self.palette.muted).pack(side='right')
        self.campaign_hub_status = self.label(panel, '', 10, fg=self.palette.accent, wraplength=980)
        self.campaign_hub_status.pack(fill='x', pady=(0, 12))
        def create():
            try:
                identifier = self.store.create_profile(new_name.get())
                self.show_campaign(identifier)
            except (ValueError, sqlite3.Error, OSError) as error:
                self.campaign_hub_status.configure(text=str(error))
        combo.bind('<<ComboboxSelected>>', lambda _event: self.show_campaign(lookup[self.campaign_profile_var.get()]))
        if not profiles:
            self.campaign_hub_status.configure(text=self.storage_error or 'Create a local profile above to start your campaign and keep earned cosmetics.')
            self.label(panel, 'Six tables. Your own trail.', 30, bold=True).pack(anchor='w', pady=24)
            self.label(panel, 'Clear stages, collect up to three stars each, and equip cosmetic rewards.\nCampaign results stay separate from standard-match statistics.',
                       13, fg=self.palette.muted, wraplength=850).pack(anchor='w')
            return
        identifier = self.campaign_profile_id = lookup[chosen]
        progress = self.campaign_progress_data = self.store.campaign_progress(identifier)
        earned = earned_cosmetics(progress)
        unlocked = available_stages(progress)
        stars = sum(row['stars'] for row in progress.values())
        cleared = sum(row['cleared'] for row in progress.values())
        self.campaign_hub_status.configure(text=self.storage_error or f'{chosen} / {cleared}/6 stages cleared / {stars}/18 best stars. Completed attempts and cosmetics are saved per profile.')
        notebook = ttk.Notebook(panel, style='Hog.TNotebook')
        notebook.pack(fill='both', expand=True)
        self.campaign_tabs = {}
        for title in ('Campaign map', 'Wardrobe', 'Milestones'):
            page = tk.Frame(notebook, bg=self.palette.panel)
            notebook.add(page, text=title)
            self.campaign_tabs[title] = page
        page = self.campaign_tabs['Campaign map']
        self.campaign_map = tk.Canvas(page, height=235, bg=self.palette.panel, highlightthickness=0)
        self.campaign_map.pack(fill='x', padx=16, pady=(8, 0))
        names = {f'{index + 1:02d} / {stage.title}': stage.identifier for index, stage in enumerate(stages())}
        default = next((stage.identifier for stage in stages() if stage.identifier in unlocked and not progress.get(stage.identifier, {}).get('cleared')), stages()[0].identifier)
        self.campaign_stage_var = tk.StringVar(self.root, next(label for label, key in names.items() if key == default))
        stage_box = ttk.Combobox(page, textvariable=self.campaign_stage_var, values=tuple(names), state='readonly', style='Hog.TCombobox')
        stage_box.pack(fill='x', padx=20, pady=8)
        self.campaign_stage_title = self.label(page, '', 18, bold=True)
        self.campaign_stage_title.pack(anchor='w', padx=22, pady=(8, 4))
        self.campaign_stage_description = self.label(page, '', 10, fg=self.palette.muted, wraplength=930)
        self.campaign_stage_description.pack(anchor='w', padx=22, pady=(0, 10))
        self.campaign_goal_labels = []
        for _ in range(3):
            label = self.label(page, '', 11)
            label.pack(anchor='w', padx=22, pady=4)
            self.campaign_goal_labels.append(label)
        bottom = tk.Frame(page, bg=self.palette.panel)
        bottom.pack(fill='x', padx=20, pady=14)
        self.campaign_start_button = self.button(bottom, 'Start stage', lambda: start())
        self.campaign_start_button.pack(side='left')
        self.campaign_stage_note = self.label(bottom, '', 9, fg=self.palette.muted, wraplength=650)
        self.campaign_stage_note.pack(side='left', padx=14)

        def select_stage(stage_id):
            self.campaign_stage_var.set(next(label for label, key in names.items() if key == stage_id))
            update_stage()

        def map_draw(_event=None):
            canvas = self.campaign_map
            canvas.delete('all')
            width = max(canvas.winfo_width(), 600)
            xs = (105, width / 2, width - 105)
            points = ((xs[0], 50), (xs[1], 50), (xs[2], 50), (xs[2], 162), (xs[1], 162), (xs[0], 162))
            for index in range(5):
                canvas.create_line(*points[index], *points[index + 1], fill=self.palette.border, width=3)
            selected = names[self.campaign_stage_var.get()]
            for index, (stage, (x, y)) in enumerate(zip(stages(), points)):
                state = progress.get(stage.identifier, {})
                color = self.palette.accent if state.get('cleared') else self.palette.gold if stage.identifier in unlocked else self.palette.muted
                tag = 'stage-' + stage.identifier
                canvas.create_oval(x-23, y-23, x+23, y+23, fill=self.palette.raised,
                                   outline=self.palette.gold if selected == stage.identifier else color,
                                   width=3 if selected == stage.identifier else 1, tags=(tag,))
                canvas.create_text(x, y, text=str(index + 1), fill=color, font=(self.family, 16, 'bold'), tags=(tag,))
                canvas.create_text(x, y+39, text=stage.title, fill=self.palette.text, font=(self.family, 10, 'bold'), tags=(tag,))
                status = f'{state.get("stars", 0)}/3 stars' if state.get('cleared') else 'Available' if stage.identifier in unlocked else 'Locked'
                canvas.create_text(x, y+56, text=status, fill=color, font=(self.family, 9), tags=(tag,))
                canvas.tag_bind(tag, '<Button-1>', lambda _event, key=stage.identifier: select_stage(key))

        def update_stage(_event=None):
            stage = stage_by_id(names[self.campaign_stage_var.get()])
            state = progress.get(stage.identifier, {})
            self.campaign_stage_title.configure(text=f'{stage.title} / {stage.opponent}')
            self.campaign_stage_description.configure(text=stage.personality + f'  Strategy: {stage.strategy}.')
            for index, (label, key) in enumerate(zip(self.campaign_goal_labels, stage.objectives)):
                label.configure(text=f'{index + 1}. ' + OBJECTIVES[key] + (' / required to clear' if index == 0 else ' / optional star'))
            allowed = stage.identifier in unlocked
            self.campaign_start_button.configure(text='Replay stage' if state.get('cleared') else 'Start stage', state='normal' if allowed else 'disabled')
            note = f'Best: {state.get("stars", 0)}/3 stars / {state.get("attempts", 0)} attempts / fixed seed {stage.seed}.' if allowed else 'Clear the previous stage to unlock this table.'
            self.campaign_stage_note.configure(text=note)
            map_draw()
        def start():
            self.start_campaign_stage(identifier, names[self.campaign_stage_var.get()])
        self.campaign_select_stage = select_stage
        stage_box.bind('<<ComboboxSelected>>', update_stage)
        self.campaign_map.bind('<Configure>', map_draw)

        equipment = self.store.equipment(identifier)
        page = self.campaign_tabs['Wardrobe']
        self.label(page, 'Cosmetics change appearance only. Preview any item; equip earned rewards.', 10,
                   fg=self.palette.muted).pack(anchor='w', padx=20, pady=16)
        wardrobe = tk.Frame(page, bg=self.palette.panel)
        wardrobe.pack(fill='both', expand=True, padx=14, pady=(0, 12))
        self.wardrobe_controls = {}
        self.wardrobe_status = self.label(page, 'Selecting a theme applies it to the entire app. Dice and avatars belong to this profile.',
                                           9, fg=self.palette.muted, wraplength=930)
        self.wardrobe_status.pack(anchor='w', padx=20, pady=(0, 16))
        earned_keys = {(item.kind, item.identifier) for item in earned}
        def wardrobe_update():
            for kind, controls in self.wardrobe_controls.items():
                item = controls['lookup'][controls['var'].get()]
                canvas = controls['canvas']
                canvas.delete('all')
                canvas.configure(bg=self.palette.panel)
                if kind == 'dice':
                    for i, value in enumerate((3, 5, 6)):
                        draw_die(canvas, 12 + i * 72, 42, 54, value, palette=self.palette, skin=item.identifier)
                elif kind == 'avatar':
                    draw_avatar(canvas, chosen, 120, self.palette, style=item.identifier)
                    canvas.move('all', 60, 15)
                else:
                    palette = PALETTES[item.identifier]
                    canvas.create_rectangle(10, 15, 225, 126, fill=palette.bg, outline=palette.border)
                    canvas.create_rectangle(23, 30, 212, 70, fill=palette.panel, outline='')
                    canvas.create_text(33, 50, text=item.title, anchor='w', fill=palette.text, font=(self.family, 11, 'bold'))
                    canvas.create_rectangle(23, 84, 105, 108, fill=palette.accent, outline='')
                    canvas.create_rectangle(118, 84, 212, 108, fill=palette.raised, outline='')
                allowed = (kind, item.identifier) in earned_keys
                controls['button'].configure(state='normal' if allowed else 'disabled')
                controls['status'].configure(text=('Earned / ready to equip' if allowed else f'Locked / needs {item.stars} stars') + (' / equipped' if equipment[kind] == item.identifier else ''))
        def equip(kind):
            item = self.wardrobe_controls[kind]['lookup'][self.wardrobe_controls[kind]['var'].get()]
            try:
                self.store.equip_cosmetic(identifier, kind, item.identifier)
                equipment[kind] = item.identifier
                if kind == 'theme':
                    self.set_theme(item.identifier)
                self.refresh_profile_art()
                self.wardrobe_status.configure(text=f'{item.title} equipped for {chosen}.' + (' Theme applied across the app.' if kind == 'theme' else ''))
                wardrobe_update()
            except (ValueError, sqlite3.Error, OSError) as error:
                self.wardrobe_status.configure(text=str(error))
        for column, kind in enumerate(('dice', 'avatar', 'theme')):
            wardrobe.columnconfigure(column, weight=1, uniform='wardrobe')
            card = self.panel(wardrobe)
            card.grid(row=0, column=column, sticky='nsew', padx=5)
            self.label(card, kind.upper(), 10, bold=True, fg=self.palette.accent).pack(anchor='w', padx=14, pady=(16, 12))
            canvas = tk.Canvas(card, height=150, width=240, bg=self.palette.panel, highlightthickness=0)
            canvas.pack(padx=8, pady=10)
            items = [item for item in cosmetics() if item.kind == kind]
            mapping = {f'{item.title} / {item.stars} stars': item for item in items}
            var = tk.StringVar(self.root, next(label for label, item in mapping.items() if item.identifier == equipment[kind]))
            box = ttk.Combobox(card, textvariable=var, values=tuple(mapping), state='readonly', style='Hog.TCombobox', width=20)
            box.pack(fill='x', padx=12, pady=10)
            status = self.label(card, '', 9, fg=self.palette.muted, wraplength=230)
            status.pack(anchor='w', padx=14, pady=10)
            button = self.button(card, 'Equip' if kind != 'theme' else 'Equip and apply', lambda selected=kind: equip(selected), kind='secondary')
            button.pack(anchor='w', padx=14, pady=12)
            self.wardrobe_controls[kind] = {'canvas': canvas, 'var': var, 'lookup': mapping, 'status': status, 'button': button}
            box.bind('<<ComboboxSelected>>', lambda _event: wardrobe_update())
        self.wardrobe_update = wardrobe_update
        page = self.campaign_tabs['Milestones']
        self.label(page, 'CAMPAIGN MILESTONES / persistent progress for this profile', 10, bold=True,
                   fg=self.palette.muted).pack(anchor='w', padx=20, pady=18)
        bars = []
        for title, value, target in campaign_achievements(progress):
            row = tk.Frame(page, bg=self.palette.panel)
            row.pack(fill='x', padx=22, pady=8)
            self.label(row, f'{title} / {value} of {target}' + (' / unlocked' if value >= target else ''), 12, bold=True).pack(anchor='w')
            bar = tk.Canvas(row, height=9, bg=self.palette.raised, highlightthickness=0)
            bar.pack(fill='x', pady=8)
            bars.append((bar, value, target))
        def bars_draw(_event=None):
            for canvas, value, target in bars:
                canvas.delete('all')
                canvas.create_rectangle(0, 0, canvas.winfo_width() * min(1, value / target), 9, fill=self.palette.accent, outline='')
        for bar, _, _ in bars:
            bar.bind('<Configure>', bars_draw)
        self.label(panel, 'Campaign attempts are separate from standard history, profile wins and the manual save slot. Only completed runs persist.',
                   9, fg=self.palette.muted, wraplength=1000).pack(anchor='w', pady=(12, 0))
        def redraw():
            self._style_insight_table()
            map_draw()
            wardrobe_update()
            bars_draw()
        self._redraw_insights = redraw
        update_stage()
        redraw()

    def start_campaign_stage(self, profile_id, stage_id):
        stage = stage_by_id(stage_id)
        progress = self.store.campaign_progress(profile_id)
        if stage_id not in available_stages(progress):
            raise ValueError('Clear the previous campaign stage first.')
        name = next(row['name'] for row in self.store.profiles() if row['id'] == profile_id)
        panel = self._insight_window(f'Campaign / {stage.title}')
        self.analysis_window.geometry('1040x840')
        self.campaign_profile_id, self.campaign_stage = profile_id, stage
        self.campaign_session = GameSession(dice=seeded_dice(stage.seed))
        self.campaign_events = []
        self.campaign_run_id = uuid4().hex
        self.campaign_paused = False
        self.campaign_result = None
        self.campaign_count = 5
        self.label(panel, f'{stage.opponent} / {stage.personality}', 10, fg=self.palette.muted, wraplength=980).pack(anchor='w', pady=(0, 14))
        scores = tk.Frame(panel, bg=self.palette.bg)
        scores.pack(fill='x', pady=(0, 12))
        self.campaign_score_labels = []
        for seat, title in enumerate((name, stage.opponent)):
            scores.columnconfigure(seat, weight=1, uniform='campaign-scores')
            card = self.panel(scores)
            card.grid(row=0, column=seat, sticky='ew', padx=(0, 6) if seat == 0 else (6, 0))
            inside = tk.Frame(card, bg=self.palette.panel)
            inside.pack(fill='x', padx=18, pady=12)
            self.avatar(inside, title, seat, 36, profile_id=profile_id if seat == 0 else None).pack(side='left', padx=(0, 12))
            self.label(inside, title, 12, bold=True).pack(side='left')
            label = self.label(inside, '0 / 100', 23, bold=True, fg=self.palette.accent if seat == 0 else self.palette.gold)
            label.pack(side='right')
            self.campaign_score_labels.append(label)
        objectives = self.panel(panel)
        objectives.pack(fill='x', pady=(0, 12))
        self.campaign_objective_labels = []
        for _ in range(3):
            label = self.label(objectives, '', 10)
            label.pack(anchor='w', padx=16, pady=5)
            self.campaign_objective_labels.append(label)
        self.campaign_dice = tk.Canvas(panel, height=90, bg=self.palette.panel, highlightthickness=0)
        self.campaign_dice.pack(fill='x')
        self.campaign_turn_result = self.label(panel, '', 11, fg=self.palette.accent, wraplength=970)
        self.campaign_turn_result.pack(fill='x', pady=10)
        selector = tk.Frame(panel, bg=self.palette.bg)
        selector.pack(fill='x')
        self.campaign_count_buttons = []
        for count in range(11):
            selector.columnconfigure(count, weight=1, uniform='campaign-dice')
            button = self.button(selector, str(count), lambda value=count: choose(value), kind='secondary')
            button.configure(padx=0)
            button.grid(row=0, column=count, sticky='ew', padx=2)
            self.campaign_count_buttons.append(button)
        actions = tk.Frame(panel, bg=self.palette.bg)
        actions.pack(fill='x', pady=12)
        self.campaign_roll_button = self.button(actions, 'Play selected dice', lambda: human())
        self.campaign_roll_button.pack(side='left')
        self.campaign_pause_button = self.button(actions, 'Pause', lambda: pause(), kind='secondary')
        self.campaign_pause_button.pack(side='left', padx=10)
        self.campaign_back_button = self.button(actions, 'Campaign map', lambda: leave(), kind='secondary')
        self.campaign_back_button.pack(side='right')
        self.campaign_status = self.label(panel, '', 11, wraplength=970, fg=self.palette.muted)
        self.campaign_status.pack(fill='x', pady=(4, 12))
        self.label(panel, f'Fixed seed {stage.seed} / immediate turn results / only completed attempts are saved.\n'
                   'Optional stars count only when the first objective clears the stage. No standard stats or save-slot changes.',
                   9, fg=self.palette.muted, wraplength=980).pack(anchor='w', side='bottom')
        def choose(count):
            if self.campaign_session.current_player == 0 and not self.campaign_paused and not self.campaign_session.finished:
                self.campaign_count = count
                draw()
        def schedule():
            if (not self.campaign_session.finished and not self.campaign_paused
                    and self.campaign_session.current_player == 1 and self.analysis_pending is None):
                self.analysis_pending = self.root.after(self.cpu_delay, cpu)
        def draw():
            session = self.campaign_session
            for seat, label in enumerate(self.campaign_score_labels):
                label.configure(text=f'{session.scores[seat]} / 100')
            checks = objective_status(stage, session, self.campaign_events)
            for label, (title, passed) in zip(self.campaign_objective_labels, checks):
                label.configure(text=('DONE / ' if passed else 'GOAL / ') + title,
                                fg=self.palette.accent if passed else self.palette.muted)
            self.campaign_dice.delete('all')
            if self.campaign_events:
                event = self.campaign_events[-1]
                skin = self.profile_equipment(profile_id)['dice'] if event.player == 0 else 'classic'
                for index, value in enumerate(event.outcomes):
                    draw_die(self.campaign_dice, 15 + index * 65, 13, 50, value, accent=value == 1, palette=self.palette, skin=skin)
                if not event.outcomes:
                    self.campaign_dice.create_text(20, 40, text='0 DICE / BOAR BRAWL', anchor='w', fill=self.palette.text, font=(self.family, 14, 'bold'))
                self.campaign_turn_result.configure(text=f'Turn {event.number} / {name if event.player == 0 else stage.opponent}: +{event.turn_points} base +{event.bonus} Sus Fuss / total {event.score_after}')
            else:
                self.campaign_turn_result.configure(text='Your opening move. Choose 0-10 dice.')
            human_turn = not session.finished and not self.campaign_paused and session.current_player == 0
            for count, button in enumerate(self.campaign_count_buttons):
                fill = self.palette.accent if count == self.campaign_count else self.palette.raised
                button.configure(state='normal' if human_turn else 'disabled', bg=fill, highlightbackground=fill,
                                 fg=self.palette.accent_text if count == self.campaign_count else self.palette.text)
            self.campaign_roll_button.configure(state='normal' if human_turn else 'disabled')
            self.campaign_pause_button.configure(text='Resume' if self.campaign_paused else 'Pause', state='disabled' if session.finished else 'normal')
            if not session.finished:
                text = 'Paused. No turns will advance.' if self.campaign_paused else 'Your turn.' if human_turn else f'{stage.opponent} is choosing...'
                self.campaign_status.configure(text=text)
            schedule()
        def finish():
            session = self.campaign_session
            record = {'config': {'names': (name, stage.opponent)}, 'scores': session.scores,
                      'events': [asdict(event) for event in self.campaign_events]}
            result = self.campaign_result = evaluate_stage(stage, record)
            try:
                self.store.record_campaign(self.campaign_run_id, profile_id, stage_id, self.campaign_events)
                text = f'{"Stage cleared" if result["cleared"] else "Stage not cleared"} / {result["stars"]}/3 stars this attempt. '
                text += 'Return to the map to see earned rewards or replay for more stars.'
            except (ValueError, sqlite3.Error, OSError) as error:
                text = f'Match finished, but campaign progress could not be saved: {error}'
            self.campaign_status.configure(text=text)
        def play(count):
            event = self.campaign_session.advance(count)
            self.campaign_events.append(event)
            draw()
            if self.campaign_session.finished:
                finish()
        def human():
            if not self.campaign_paused and not self.campaign_session.finished and self.campaign_session.current_player == 0:
                play(self.campaign_count)
        def cpu():
            self.analysis_pending = None
            session = self.campaign_session
            if session.finished or self.campaign_paused or session.current_player != 1:
                return
            if stage.strategy == 'hard' and not self.policy_future.done():
                self.analysis_pending = self.root.after(30, cpu)
                return
            count = STRATEGIES[stage.strategy][0](session.scores[1], session.scores[0])
            play(count)
        def pause():
            if self.campaign_session.finished:
                return
            self.campaign_paused = not self.campaign_paused
            if self.analysis_pending is not None:
                self.root.after_cancel(self.analysis_pending)
                self.analysis_pending = None
            draw()
        def leave():
            if not self.campaign_session.finished:
                was_paused = self.campaign_paused
                if not was_paused:
                    pause()
                if not messagebox.askyesno('Leave campaign attempt?', 'Only completed campaign attempts are saved. Leave this unfinished run?', parent=self.analysis_window):
                    if not was_paused:
                        pause()
                    return
            self.show_campaign(profile_id)
        self.campaign_cpu = cpu
        self.campaign_draw = draw
        self._redraw_insights = draw
        self.analysis_window.protocol('WM_DELETE_WINDOW', leave)
        draw()
