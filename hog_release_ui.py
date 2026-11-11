"""v4 welcome tour, controls, profile management and portable data tools."""

from dataclasses import replace
from datetime import datetime
from pathlib import Path
import sqlite3
import traceback
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except ImportError:
    tk = None

from hog_backup import export_backup, prepare_backup, restore_backup, discard_prepared
from hog_controls import ACTIONS, DEFAULT_KEYS, KEY_CHOICES, validate_shortcuts


class ReleaseUI:
    def show_welcome(self):
        panel = self.analysis_shell('Welcome to Hog')
        self.analysis_window.geometry('840x690')
        page = [0]
        self.label(panel, 'WELCOME / HOG 4.0', 10, bold=True, fg=self.palette.accent).pack(anchor='w')
        progress = self.label(panel, '', 10, fg=self.palette.muted)
        progress.pack(anchor='w', pady=(12, 18))
        content = self.panel(panel)
        content.pack(fill='both', expand=True)
        bar = tk.Frame(panel, bg=self.palette.bg)
        bar.pack(fill='x', pady=(18, 0))
        pages = (
            ('Your table. Your pace.', 'Play locally without an account, learn with the coach, or invite a friend to a private multiplayer room.',
             ('PLAY / Race to 100 with three special scoring rules.', 'LEARN / Guided lessons, practice positions and eight puzzles.', 'EXPLORE / Campaign rewards, replay analysis and tournaments.')),
            ('Three rules, one decision.', 'On your turn, choose 0-10 dice. All chosen dice are consumed, even after a 1 appears.',
             ('SOW SAD / Any rolled 1 makes the base turn worth 1.', 'BOAR BRAWL / Zero dice: max(1, 3 x abs(opponent tens - your ones)).', 'SUS FUSS / A total with 3 or 4 factors rises to the next prime.')),
            ('Make it comfortable.', 'Use Tab and Shift+Tab to move focus. Space or Enter activates a focused button. Digits choose dice on the main game table.',
             ('PRESENTATION / Theme, larger text, reduced motion and sound.', 'CONTROLS / Remap nine actions in Settings > Edit controls.', 'PROFILES / Keep local statistics and campaign rewards per player.')),
            ('Keep your progress.', 'Settings > Backup & recovery exports a portable file. Import previews its contents and saves your current data before replacing it.',
             ('MANUAL SAVE / Pause and save an unfinished standard match.', 'BACKUP / Includes profiles, history, campaign, equipment and settings.', 'ONLINE / Requires a separate reachable relay; see ONLINE.md.')),
        )

        def finish():
            self.preferences = replace(self.preferences, welcome_seen=True)
            self._persist_preferences()
            self.close_analysis()

        def draw():
            for child in content.winfo_children(): child.destroy()
            title, text, facts = pages[page[0]]
            progress.configure(text=f'Step {page[0]+1} of {len(pages)}  /  You can reopen this tour from Settings.')
            self.label(content, title, 25, bold=True, wraplength=720).pack(anchor='w', padx=24, pady=(25, 16))
            self.label(content, text, 12, fg=self.palette.muted, wraplength=700).pack(anchor='w', padx=24, pady=(0, 20))
            for fact in facts:
                self.label(content, fact, 11, wraplength=700).pack(anchor='w', padx=24, pady=10)
            back.configure(state='normal' if page[0] else 'disabled')
            next_button.configure(text='Finish tour' if page[0] == 3 else 'Next step  >')

        def advance(delta):
            if page[0] == 3 and delta == 1:
                finish()
            else:
                page[0] += delta
                draw()
        self.button(bar, 'Skip tour', finish, kind='secondary').pack(side='left')
        next_button = self.button(bar, 'Next step  >', lambda: advance(1))
        next_button.pack(side='right')
        back = self.button(bar, '<  Back', lambda: advance(-1), kind='secondary')
        back.pack(side='right', padx=10)
        self.welcome_next_button = next_button
        self.welcome_back_button = back
        self.welcome_step = page
        draw()
        next_button.focus_set()

    def show_controls(self):
        panel = self.analysis_shell('Keyboard controls')
        self.analysis_window.geometry('760x730')
        self.label(panel, 'Choose a unique letter, function key, Return or Escape for each action.',
                   11, fg=self.palette.muted, wraplength=690).pack(anchor='w')
        self.label(panel, 'Digits 0-9 remain fixed. Shortcuts apply to the main window; typing fields keep their keys.',
                   10, fg=self.palette.muted, wraplength=690).pack(anchor='w', pady=(6, 16))
        grid = tk.Frame(panel, bg=self.palette.bg)
        grid.pack(fill='x')
        self.control_vars = []
        for row, (action, key) in enumerate(zip(ACTIONS, self.preferences.shortcuts)):
            self.label(grid, action, 11).grid(row=row, column=0, sticky='w', pady=5)
            variable = tk.StringVar(self.root, key)
            self.control_vars.append(variable)
            ttk.Combobox(grid, textvariable=variable, values=KEY_CHOICES, state='readonly',
                         width=18, style='Hog.TCombobox').grid(row=row, column=1, sticky='e', pady=5)
        grid.columnconfigure(1, weight=1)
        self.controls_status = self.label(panel, 'Changes take effect after Apply controls.', 10,
                                          fg=self.palette.muted, wraplength=690)
        self.controls_status.pack(anchor='w', pady=15)

        def apply():
            try:
                keys = validate_shortcuts([variable.get() for variable in self.control_vars])
                self.preferences = replace(self.preferences, shortcuts=keys)
                if self.screen == "game": self._refresh_controls()
                self._persist_preferences()
                self.controls_status.configure(text=self.settings_save_error or 'Controls saved. Tab / Shift+Tab and Space / Enter remain available.')
            except ValueError as error:
                self.controls_status.configure(text=str(error))

        def defaults():
            for variable, key in zip(self.control_vars, DEFAULT_KEYS): variable.set(key)
            self.controls_status.configure(text='Defaults selected. Apply controls to save.')
        actions = tk.Frame(panel, bg=self.palette.bg)
        actions.pack(fill='x')
        self.controls_apply_button = self.button(actions, 'Apply controls', apply)
        self.controls_apply_button.pack(side='left')
        self.button(actions, 'Reset defaults', defaults, kind='secondary').pack(side='left', padx=10)

    def show_profile_manager(self):
        panel = self.analysis_shell('Manage profiles')
        self.analysis_window.geometry('880x700')
        self.label(panel, 'Rename profiles or archive them from setup lists. History, rewards and saved games are preserved.',
                   11, fg=self.palette.muted, wraplength=800).pack(anchor='w', pady=(0, 18))
        body = tk.Frame(panel, bg=self.palette.bg)
        body.pack(fill='both', expand=True)
        listing = self.profile_manager_list = tk.Listbox(body, bg=self.palette.panel, fg=self.palette.text,
                    selectbackground=self.palette.accent, selectforeground=self.palette.accent_text,
                    width=32, exportselection=False, relief='flat', highlightthickness=2,
                    highlightcolor=self.palette.gold)
        listing.pack(side='left', fill='both', expand=True, padx=(0, 22))
        right = tk.Frame(body, bg=self.palette.bg)
        right.pack(side='left', fill='both', expand=True)
        self.label(right, 'Profile name', 11, bold=True).pack(anchor='w', pady=(10, 8))
        variable = self.profile_rename_var = tk.StringVar(self.root)
        tk.Entry(right, textvariable=variable, width=25, bg=self.palette.panel, fg=self.palette.text, insertbackground=self.palette.text, relief='flat').pack(fill='x', ipady=8)
        status = self.profile_manager_status = self.label(right, 'Choose a profile.', 10, fg=self.palette.muted, wraplength=360)
        status.pack(anchor='w', pady=18)
        rows = []

        def selected(_event=None):
            if not listing.curselection(): return
            row = rows[listing.curselection()[0]]
            variable.set(row['name'])
            archive.configure(text='Restore profile' if row['archived'] else 'Archive profile')
            status.configure(text='Archived: hidden from new setup lists.' if row['archived'] else 'Active profile. Previous match names remain historical.')

        def refresh(identifier=None):
            rows[:] = self.store.profiles(True)
            listing.delete(0, 'end')
            for row in rows: listing.insert('end', row['name'] + ('  [archived]' if row['archived'] else ''))
            if rows:
                index = next((i for i, row in enumerate(rows) if row['id'] == identifier), 0)
                listing.selection_set(index); selected()

        def mutate(archive_action=False):
            if not listing.curselection(): return
            row = rows[listing.curselection()[0]]
            try:
                if archive_action:
                    self.store.archive_profile(row['id'], not bool(row['archived']))
                else:
                    self.store.rename_profile(row['id'], variable.get())
                refresh(row['id'])
                if self.screen == 'home': self.show_home()
                elif self.screen == 'setup': self.show_setup(self.mode_var.get())
            except (ValueError, sqlite3.Error) as error:
                status.configure(text=str(error))
        self.profile_rename_button = self.button(right, 'Rename profile', mutate)
        self.profile_rename_button.pack(anchor='w')
        archive = self.profile_archive_button = self.button(right, 'Archive profile', lambda: mutate(True), kind='secondary')
        archive.pack(anchor='w', pady=12)
        listing.bind('<<ListboxSelect>>', selected)
        refresh()

    def show_data_center(self):
        panel = self.analysis_shell('Backup & recovery')
        self.analysis_window.geometry('880x730')
        self.label(panel, 'YOUR PROGRESS, PORTABLE', 10, bold=True, fg=self.palette.accent).pack(anchor='w')
        self.label(panel, 'Export, review, restore.', 26, bold=True).pack(anchor='w', pady=(8, 14))
        self.label(panel, 'Export includes all local profiles, completed matches, the manual save, tournaments, campaign runs, equipment and preferences. Online rooms and unfinished campaign runs are temporary.',
                   11, fg=self.palette.muted, wraplength=790).pack(anchor='w')
        self.label(panel, 'Restore replaces local data. It does not merge. Finish or leave active games and online rooms first. A safety backup must succeed before restore.',
                   11, wraplength=790).pack(anchor='w', pady=14)
        counts = self.store.connection.execute('SELECT COUNT(*) FROM profiles').fetchone()[0]
        self.label(panel, f'Current data: {counts} profiles / {len(self.store.history())} completed matches / {len(self.store.tournaments())} tournaments',
                   11, bold=True, wraplength=790).pack(anchor='w', pady=8)
        actions = tk.Frame(panel, bg=self.palette.bg)
        actions.pack(fill='x', pady=16)
        self.button(actions, 'Export backup', self.export_portable_backup).pack(side='left')
        self.button(actions, 'Choose backup to preview', self.preview_portable_backup, kind='secondary').pack(side='left', padx=12)
        self.backup_preview = self.label(panel, 'No backup selected. Files are validated in isolation before restore.',
                                         11, fg=self.palette.muted, wraplength=790)
        self.backup_preview.pack(anchor='w', pady=12)
        self.backup_restore_button = self.button(panel, 'Restore selected backup', self.apply_portable_backup, state='disabled')
        self.backup_restore_button.pack(anchor='w', pady=8)
        self.backup_status = self.label(panel, self.storage_error or 'Portable format: bounded JSON with a damage-detection checksum.',
                                       10, fg=self.palette.muted, wraplength=790)
        self.backup_status.pack(anchor='w', pady=14)

    def export_portable_backup(self):
        path = filedialog.asksaveasfilename(parent=self.analysis_window, defaultextension='.hogbackup',
                    initialfile='hog-progress.hogbackup', filetypes=(('Hog backup', '*.hogbackup'),))
        if path:
            try:
                export_backup(path, self.store, self.preferences)
                self.backup_status.configure(text=f'Backup exported: {Path(path).name}')
            except (OSError, ValueError, sqlite3.Error) as error:
                self.backup_status.configure(text=f'Export failed: {error}')

    def preview_portable_backup(self, path=None):
        path = path or filedialog.askopenfilename(parent=self.analysis_window, filetypes=(('Hog backup', '*.hogbackup'),))
        if not path: return
        if self.backup_candidate is not None:
            self.backup_candidate.close(); self.backup_candidate = None
        self.backup_restore_button.configure(state='disabled')
        if self.backup_future is not None:
            self.backup_future.add_done_callback(discard_prepared)
            self.backup_future.cancel()
        if self.analysis_pending is not None:
            self.root.after_cancel(self.analysis_pending)
            self.analysis_pending = None
        self.backup_status.configure(text='Validating backup in the background. Your current data is unchanged.')
        self.backup_preview.configure(text='Checking identities, scoring, saved dice state, campaign rewards and preferences...')
        future = self.backup_future = self.worker.submit(prepare_backup, path)
        self.poll_backup(future)

    def poll_backup(self, future):
        if self.backup_future is not future:
            return
        self.analysis_pending = None
        if not future.done():
            self.analysis_pending = self.root.after(30, lambda: self.poll_backup(future))
            return
        self.backup_future = None
        try:
            self.backup_candidate = future.result()
            counts = self.backup_candidate.counts
            self.backup_preview.configure(text=f"VALIDATED / Hog {self.backup_candidate.version}\nCreated: {self.backup_candidate.created_at}\n{counts['profiles']} profiles / {counts['matches']} matches / {counts['campaign_runs']} campaign runs\n{counts['tournaments']} tournaments / {counts['saves']} manual save / {counts['profile_archive']} archived profiles")
            self.backup_restore_button.configure(state='normal')
            self.backup_status.configure(text='Ready for review. Restore requires confirmation and creates a safety copy.')
        except (OSError, ValueError) as error:
            self.backup_preview.configure(text='No valid backup selected.')
            self.backup_status.configure(text=str(error))

    def apply_portable_backup(self):
        if self.backup_candidate is None: return
        active = (self.session is not None and not self.session.finished)
        campaign = getattr(self, 'campaign_session', None)
        if active or (campaign is not None and not campaign.finished) or getattr(getattr(self, 'online_client', None), 'token', None):
            self.backup_status.configure(text='Finish or leave active matches, campaign runs and online rooms before restoring.')
            return
        if not messagebox.askyesno('Replace local data?', 'Replace all current local progress with this backup? A safety copy will be saved first.', parent=self.analysis_window): return
        folder = self.preferences_path.parent if self.preferences_path else Path.home() / '.hog-recovery'
        safety = folder / 'backups' / ('before-restore-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.hogbackup')
        try:
            preferences = restore_backup(self.backup_candidate, self.store, safety, self.preferences)
        except (OSError, ValueError, sqlite3.Error) as error:
            self.backup_status.configure(text=f'Restore failed: {error}')
            return
        self.session = None
        self.close_analysis()
        self.show_home()
        self.set_theme(preferences.theme)
        self.preferences = preferences
        self.set_pace(preferences.pace)
        self.set_sound(preferences.sound)
        self.set_large_text(preferences.large_text)
        self._persist_preferences()
        self.show_data_center()
        self.backup_status.configure(text=f'Restored. Safety copy: {safety}' + ('\n' + self.settings_save_error if self.settings_save_error else ''))

    def handle_callback_error(self, kind, error, trace):
        """Pause uncertain state; never repeat a failed action automatically."""
        self.cancel_pending()
        self._cancel_ui()
        self.paused = True
        self.audio.stop()
        diagnostic = 'Diagnostic file could not be written.'
        if self.preferences_path is not None:
            try:
                path = self.preferences_path.parent / 'last-error.log'
                path.parent.mkdir(parents=True, exist_ok=True)
                # Only exception type and code locations: no locals, tokens or message payload.
                lines = [kind.__name__] + [f'{Path(frame.filename).name}:{frame.lineno} in {frame.name}' for frame in traceback.extract_tb(trace)]
                path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
                diagnostic = f'Diagnostic: {path}'
            except OSError:
                pass
        messagebox.showerror('Hog paused after an error',
            'An action could not finish. The local match has been paused. Review the table before resuming, or return to the dashboard. You can export current progress from Settings > Backup & recovery.\n\n' + diagnostic,
            parent=self.root)
