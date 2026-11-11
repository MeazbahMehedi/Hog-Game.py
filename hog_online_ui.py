"""Tk multiplayer views; HTTP work runs on a dedicated single-worker executor."""

from concurrent.futures import ThreadPoolExecutor
import time
from uuid import uuid4
try:
    import tkinter as tk
    from tkinter import ttk, filedialog
except ImportError:
    tk = None

from hog_online_client import OnlineClient, NetworkError
from hog_drawing import draw_die


class OnlineUI:
    def close_online_view(self):
        self.online_view_active = False

    def shutdown_online(self):
        self.online_view_active = False
        executor = getattr(self, 'online_executor', None)
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)

    def show_online(self):
        panel = self._insight_window('Private multiplayer / play together')
        self.online_view_active = True
        if not hasattr(self, 'online_executor'):
            self.online_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='hog-network')
            self.online_client = None
            self.online_future = None
            self.online_command = None
            self.online_state = None
            self.online_address_var = tk.StringVar(self.root, 'http://127.0.0.1:8765')
            self.online_name_var = tk.StringVar(self.root, 'Player')
            self.online_code_var = tk.StringVar(self.root)
            self.online_ca_var = tk.StringVar(self.root)
        self.online_busy = False
        self.online_room_built = False
        self.online_panel = panel
        self.online_connection_label = self.label(panel, 'Connect to a relay you or your friend runs.', 10,
                                                  fg=self.palette.accent, wraplength=930)
        self.online_connection_label.pack(fill='x', pady=(0, 12))
        self.online_content = tk.Frame(panel, bg=self.palette.bg)
        self.online_content.pack(fill='both', expand=True)
        self._redraw_insights = self.online_redraw
        if self.online_future is not None:
            self.online_setup()
            self.online_busy = True
            self.online_connection_label.configure(text='Finishing the previous connection request...')
            self.online_watch()
        elif self.online_client is not None and self.online_client.token:
            self.online_connection_label.configure(text='Reconnecting to your reserved seat...')
            self.online_submit('state', {})
        else:
            self.online_setup()

    def online_setup(self):
        self.online_room_built = False
        for child in self.online_content.winfo_children():
            child.destroy()
        self.label(self.online_content, 'Your table, wherever you play.', 26, bold=True).pack(anchor='w', pady=(4, 12))
        self.label(self.online_content, 'Start the included relay, enter its address, then create a room or join a friend.\n'
                   'Local test: python hog_server.py   /   LAN and HTTPS instructions: ONLINE.md',
                   11, fg=self.palette.muted, wraplength=910).pack(anchor='w', pady=(0, 22))
        form = self.panel(self.online_content)
        form.pack(fill='x')
        inner = tk.Frame(form, bg=self.palette.panel)
        inner.pack(fill='x', padx=22, pady=20)
        for label, variable in (('Server URL', self.online_address_var), ('Display name', self.online_name_var),
                                ('Room code (join only)', self.online_code_var)):
            self.label(inner, label, 10, fg=self.palette.muted).pack(anchor='w', pady=(0, 5))
            tk.Entry(inner, textvariable=variable, bg=self.palette.bg, fg=self.palette.text,
                     insertbackground=self.palette.text, relief='flat').pack(fill='x', ipady=9, pady=(0, 14))
        options = tk.Frame(inner, bg=self.palette.panel)
        options.pack(fill='x', pady=(0, 14))
        self.label(options, 'Turn timer', 10, fg=self.palette.muted).pack(side='left')
        self.online_timer_var = tk.StringVar(self.root, '60')
        ttk.Combobox(options, textvariable=self.online_timer_var, values=('0', '30', '60', '120'),
                     state='readonly', style='Hog.TCombobox', width=6).pack(side='left', padx=12)
        self.label(options, 'seconds / 0 disables it / host chooses', 9, fg=self.palette.muted).pack(side='left')
        ca = tk.Frame(inner, bg=self.palette.panel)
        ca.pack(fill='x')
        self.label(ca, 'Optional trusted CA file', 9, fg=self.palette.muted).pack(side='left')
        tk.Entry(ca, textvariable=self.online_ca_var, width=36, relief='flat', bg=self.palette.bg,
                 fg=self.palette.text, insertbackground=self.palette.text).pack(side='left', padx=10, ipady=6)
        def choose_ca():
            path = filedialog.askopenfilename(parent=self.analysis_window, filetypes=(('PEM certificate', '*.pem *.crt'), ('All files', '*')))
            if path:
                self.online_ca_var.set(path)
        self.button(ca, 'Browse', choose_ca, kind='secondary').pack(side='left')
        actions = tk.Frame(self.online_content, bg=self.palette.bg)
        actions.pack(fill='x', pady=18)
        self.online_create_button = self.button(actions, 'Create private room', lambda: self.online_connect('create'))
        self.online_create_button.pack(side='left')
        self.online_join_button = self.button(actions, 'Join room', lambda: self.online_connect('join'), kind='secondary')
        self.online_join_button.pack(side='left', padx=12)
        self.label(self.online_content, 'Use HTTP for a trusted local network; use HTTPS across the internet. Certificate checks stay enabled.\n'
                   'Private rooms have no cloud account. Online results do not alter local profile wins, campaign stars or saves.',
                   10, fg=self.palette.muted, wraplength=930).pack(anchor='w', pady=8)

    def online_connect(self, operation):
        if self.online_busy:
            return
        try:
            self.online_client = OnlineClient(self.online_address_var.get(), cafile=self.online_ca_var.get().strip() or None)
            payload = {'name': self.online_name_var.get(), 'request_id': uuid4().hex}
            if operation == 'create':
                payload['turn_seconds'] = int(self.online_timer_var.get())
            else:
                payload['room'] = self.online_code_var.get().strip().upper()
        except (ValueError, OSError) as failure:
            self.online_connection_label.configure(text=f'Check connection settings: {failure}')
            return
        self.online_connection_label.configure(text='Connecting to the relay...')
        self.online_submit(operation, payload)

    def online_submit(self, operation, payload):
        if not getattr(self, 'online_view_active', False) or self.online_client is None:
            return
        if self.online_future is not None and not self.online_future.done():
            return
        if self.analysis_pending is not None:
            self.root.after_cancel(self.analysis_pending)
            self.analysis_pending = None
        self.online_busy = True
        self.online_command = (operation, dict(payload))
        self.online_future = self.online_executor.submit(self.online_client.call, operation, payload)
        if self.online_room_built:
            self.online_redraw()
        else:
            for name in ('online_create_button', 'online_join_button'):
                button = getattr(self, name, None)
                if button is not None and button.winfo_exists():
                    button.configure(state='disabled')
        self.online_watch()

    def online_watch(self):
        self.analysis_pending = None
        if not getattr(self, 'online_view_active', False) or self.analysis_window is None:
            return
        if self.online_future is None:
            return
        if not self.online_future.done():
            self.analysis_pending = self.root.after(30, self.online_watch)
            return
        future, self.online_future = self.online_future, None
        operation, payload = self.online_command
        self.online_busy = False
        try:
            result = future.result()
        except NetworkError as failure:
            if operation == 'leave':
                self.online_client = None
                self.online_state = None
                self.online_setup()
                self.online_connection_label.configure(text='Disconnected. The relay may retain an unreachable seat until its grace period expires.')
                return
            self.online_connection_label.configure(text=str(failure) + (' Retrying the same request...' if failure.status in (None, 429, 503) else ''))
            if failure.status in (None, 429, 503):
                self.online_busy = True
                if self.online_room_built:
                    self.online_redraw()
                self.analysis_pending = self.root.after(1800, lambda: self.online_submit(operation, payload))
            elif failure.status in (401, 404) or not self.online_client.token:
                self.online_client = None
                self.online_state = None
                self.online_setup()
            else:
                self.analysis_pending = self.root.after(300, lambda: self.online_submit('state', {}))
            return
        except Exception:
            self.online_connection_label.configure(text='Connection could not complete. Check the relay address and try again.')
            self.online_setup()
            return
        if result.get('left'):
            self.online_client = None
            self.online_state = None
            self.online_setup()
            self.online_connection_label.configure(text='You left the room. Create or join another table.')
            return
        self.online_state = result['state']
        self.online_received_at = time.monotonic()
        if not self.online_room_built:
            self.online_build_room()
        self.online_connection_label.configure(text='Connected / synchronized with the relay. Closing this window disconnects; reopen Online to reconnect within the grace period.')
        self.online_redraw()
        self.analysis_pending = self.root.after(600, lambda: self.online_submit('state', {}))

    def online_build_room(self):
        for child in self.online_content.winfo_children():
            child.destroy()
        self.online_room_built = True
        self.online_count = 5
        top = tk.Frame(self.online_content, bg=self.palette.bg)
        top.pack(fill='x', pady=(0, 10))
        self.online_room_label = self.label(top, '', 18, bold=True)
        self.online_room_label.pack(side='left')
        self.button(top, 'Copy code', self.online_copy_code, kind='secondary').pack(side='right')
        self.online_server_label = self.label(self.online_content, self.online_client.endpoint, 9, fg=self.palette.muted)
        self.online_server_label.pack(anchor='w', pady=(0, 10))
        cards = tk.Frame(self.online_content, bg=self.palette.bg)
        cards.pack(fill='x')
        self.online_name_labels, self.online_score_labels, self.online_presence_labels = [], [], []
        for seat in (0, 1):
            cards.columnconfigure(seat, weight=1, uniform='online-players')
            card = self.panel(cards)
            card.grid(row=0, column=seat, sticky='ew', padx=(0, 6) if seat == 0 else (6, 0))
            inside = tk.Frame(card, bg=self.palette.panel)
            inside.pack(fill='x', padx=18, pady=12)
            name = self.label(inside, '', 14, bold=True)
            name.pack(anchor='w')
            score = self.label(inside, '0 / 100', 29, bold=True, fg=self.palette.accent if seat == 0 else self.palette.gold)
            score.pack(anchor='w', pady=3)
            presence = self.label(inside, '', 9, fg=self.palette.muted)
            presence.pack(anchor='w')
            self.online_name_labels.append(name);self.online_score_labels.append(score);self.online_presence_labels.append(presence)
        self.online_turn_label = self.label(self.online_content, '', 11, bold=True, fg=self.palette.accent, wraplength=930)
        self.online_turn_label.pack(fill='x', pady=12)
        self.online_dice_canvas = tk.Canvas(self.online_content, height=80, bg=self.palette.panel, highlightthickness=0)
        self.online_dice_canvas.pack(fill='x')
        self.online_result_label = self.label(self.online_content, '', 10, fg=self.palette.muted, wraplength=930)
        self.online_result_label.pack(fill='x', pady=8)
        selector = tk.Frame(self.online_content, bg=self.palette.bg)
        selector.pack(fill='x')
        self.online_count_buttons = []
        for count in range(11):
            selector.columnconfigure(count, weight=1, uniform='online-dice')
            button = self.button(selector, str(count), lambda choice=count: self.online_choose(choice), kind='secondary')
            button.configure(padx=0, pady=7)
            button.grid(row=0, column=count, sticky='ew', padx=2)
            self.online_count_buttons.append(button)
        actions = tk.Frame(self.online_content, bg=self.palette.bg)
        actions.pack(fill='x', pady=12)
        self.online_move_button = self.button(actions, 'Play selected dice', self.online_move)
        self.online_move_button.pack(side='left')
        self.online_ready_button = self.button(actions, 'Ready', self.online_ready, kind='secondary')
        self.online_ready_button.pack(side='left', padx=8)
        self.online_rematch_button = self.button(actions, 'Rematch', self.online_rematch, kind='secondary')
        self.online_rematch_button.pack(side='left')
        self.online_leave_button = self.button(actions, 'Leave room', lambda: self.online_submit('leave', {}), kind='secondary')
        self.online_leave_button.pack(side='right')
        self.online_disconnect_button = self.button(actions, 'Disconnect', self.close_analysis, kind='secondary')
        self.online_disconnect_button.pack(side='right', padx=8)
        journal_frame = tk.Frame(self.online_content, bg=self.palette.panel)
        journal_frame.pack(fill='both', expand=True)
        journal_scroll = ttk.Scrollbar(journal_frame, orient='vertical')
        journal_scroll.pack(side='right', fill='y')
        self.online_journal = tk.Text(journal_frame, bg=self.palette.panel, fg=self.palette.text, relief='flat',
                                     height=5, wrap='word', padx=12, pady=10, font=(self.family, 10), state='disabled', yscrollcommand=journal_scroll.set)
        self.online_journal.pack(fill='both', expand=True)
        journal_scroll.configure(command=self.online_journal.yview)
        self.label(self.online_content, 'Server rolls and validates every turn. A connected player timeout automatically takes zero dice.\n'
                   'Disconnect pauses the turn timer after the heartbeat threshold; reconnect within 90 seconds. Online results stay separate from local data.',
                   9, fg=self.palette.muted, wraplength=930).pack(anchor='w', pady=(10, 0))

    def online_choose(self, count):
        if not self.online_busy:
            self.online_count = count
            self.online_redraw()

    def online_move(self):
        if self.online_state and not self.online_busy:
            self.online_submit('move', self.online_client.move_payload(self.online_state, self.online_count))

    def online_ready(self):
        if self.online_state and not self.online_busy:
            you = self.online_state['you']
            player = self.online_state['players'][you]
            self.online_submit('ready', {'ready': not player['ready']})

    def online_rematch(self):
        if self.online_state and not self.online_busy:
            you = self.online_state['you']
            player = self.online_state['players'][you]
            self.online_submit('rematch', {'ready': not player['rematch']})

    def online_copy_code(self):
        if self.online_state:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.online_state['room'])

    def online_redraw(self):
        if not getattr(self, 'online_view_active', False) or not self.online_room_built or not self.online_state:
            return
        state = self.online_state
        you, phase = state['you'], state['phase']
        self.online_room_label.configure(text=f'ROOM {state["room"]} / ' + ('LOBBY' if state['phase'] == 'lobby' else f'ROUND {state["round"]}'))
        for seat in (0, 1):
            player = state['players'][seat]
            self.online_name_labels[seat].configure(text=(player['name'] if player else 'Waiting for a player') + (' / YOU' if seat == you else ''))
            self.online_score_labels[seat].configure(text=f'{state["scores"][seat]} / 100')
            presence = 'Empty seat' if not player else ('Connected' if player['connected'] else f'Disconnected / {player["reconnect_remaining"]:.0f}s to reconnect')
            if player and phase == 'lobby':
                presence += ' / Ready' if player['ready'] else ' / Not ready'
            elif player and phase == 'finished':
                presence += ' / Rematch requested' if player['rematch'] else ''
            self.online_presence_labels[seat].configure(text=presence)
        if phase == 'lobby':
            text = 'Share the room code and server address. Both players must press Ready.'
        elif phase == 'finished':
            result = state['result']
            winner = result['winner']
            text = ('Round ended without a winner.' if winner is None else f'{state["match_names"][winner]} wins the round.') + f' Reason: {result["reason"]}. Both players can request a rematch; the starting seat alternates.'
        elif state['paused']:
            text = 'Connection pause / the turn timer is held while a player reconnects.'
        else:
            timer = 'timer disabled' if state['turn_remaining'] is None else f'{state["turn_remaining"]:.0f}s remaining'
            text = f'Turn {state["turn"]} / {"Your turn" if state["current_player"] == you else "Opponent turn"} / {timer}'
        self.online_turn_label.configure(text=text)
        can_move = phase == 'playing' and not state['paused'] and state['current_player'] == you and not self.online_busy
        for count, button in enumerate(self.online_count_buttons):
            fill = self.palette.accent if count == self.online_count else self.palette.raised
            button.configure(state='normal' if can_move else 'disabled', bg=fill, highlightbackground=fill,
                             fg=self.palette.accent_text if count == self.online_count else self.palette.text)
        self.online_move_button.configure(state='normal' if can_move else 'disabled')
        self.online_ready_button.configure(state='normal' if phase == 'lobby' and not self.online_busy else 'disabled',
                                           text='Not ready' if phase == 'lobby' and state['players'][you] and state['players'][you]['ready'] else 'Ready')
        self.online_rematch_button.configure(state='normal' if phase == 'finished' and not self.online_busy else 'disabled',
                                             text='Cancel rematch' if state['players'][you] and state['players'][you]['rematch'] else 'Rematch')
        self.online_leave_button.configure(state='normal' if not self.online_busy else 'disabled')
        canvas = self.online_dice_canvas
        canvas.delete('all')
        if state['events']:
            wrapped = state['events'][-1]
            event = wrapped['event']
            for index, value in enumerate(event['outcomes']):
                draw_die(canvas, 14 + index * 62, 10, 46, value, accent=value == 1, palette=self.palette)
            if not event['outcomes']:
                canvas.create_text(18, 34, text='0 DICE / BOAR BRAWL', anchor='w', fill=self.palette.text, font=(self.family, 13, 'bold'))
            bonus = event['score_after'] - event['score_before'] - event['turn_points']
            self.online_result_label.configure(text=f'Turn {event["number"]}: +{event["turn_points"]} base +{bonus} bonus / total {event["score_after"]}' + (' / automatic timeout move' if wrapped['automatic'] else ''))
        else:
            self.online_result_label.configure(text='Every scoring roll is generated once by the relay.')
        self.online_journal.configure(state='normal')
        self.online_journal.delete('1.0', 'end')
        for wrapped in state['events']:
            event = wrapped['event']
            name = state['match_names'][event['player']]
            self.online_journal.insert('end', f'{event["number"]:02d} / {name} / {event["num_rolls"]} dice / {event["score_before"]} -> {event["score_after"]}' + (' / timeout' if wrapped['automatic'] else '') + '\n')
        self.online_journal.configure(state='disabled')
        self.online_journal.see('end')
