"""Model-based decisions, pre-roll review, puzzle ties and actual Tk learning views."""

from dataclasses import asdict, replace
from copy import deepcopy
import json
import unittest

from hog import GameSession, TurnEvent, seeded_dice
from hog_ai import analyze_moves
from hog_coach import (coach_position, explain_choice, review_match, puzzles,
                       check_answer, TIE_TOLERANCE)
from hog_desktop import HogApp, tk
from hog_match import MatchConfig
from hog_preferences import Preferences


def example(seed=42):
    config = MatchConfig(2, ('Alice', 'Bob'), seed=seed)
    session = GameSession(dice=seeded_dice(seed))
    events = []
    while not session.finished:
        events.append(session.advance((session.turn_number * 3) % 11))
    record = {'config': asdict(config), 'scores': session.scores, 'events': [asdict(event) for event in events]}
    return config, session, events, record


class CoachingTests(unittest.TestCase):
    def test_coach_values_equal_existing_exact_analysis(self):
        report = coach_position(37, 81)
        self.assertEqual(report.moves, analyze_moves(37, 81))
        self.assertTrue(report.best_choices)
        best = max(row.win_probability for row in report.moves)
        for count in report.best_choices:
            self.assertLessEqual(best - report.moves[count].win_probability, TIE_TOLERANCE)

    def test_zero_dice_finish_is_guaranteed(self):
        report = coach_position(98, 90)
        self.assertEqual(report.finish_chances[0], 1)
        self.assertIn(0, report.best_choices)
        self.assertIn('for every modeled dice outcome', explain_choice(report, report.recommended))
        self.assertIn('guaranteed finish was available', explain_choice(report, 1))

    def test_one_point_from_goal_all_moves_finish(self):
        # Every legal move earns at least one point.
        report = coach_position(99, 99)
        for chance in report.finish_chances:
            self.assertAlmostEqual(chance, 1)

    def test_one_die_immediate_finish_chance_is_exact(self):
        # At 95, faces 5 and 6 finish; the other four outcomes do not.
        self.assertAlmostEqual(coach_position(95, 70).finish_chances[1], 1 / 3)

    def test_all_legal_ties_are_accepted(self):
        puzzle = puzzles()[-1]
        report = coach_position(puzzle.score, puzzle.opponent)
        self.assertEqual(report.best_choices, tuple(range(11)))
        self.assertTrue(all(check_answer(puzzle, count)[0] for count in range(11)))

    def test_puzzles_have_valid_distinct_positions_and_model_answers(self):
        catalog = puzzles()
        self.assertEqual(len(catalog), 8)
        self.assertEqual(len({p.identifier for p in catalog}), 8)
        for puzzle in catalog:
            report = coach_position(puzzle.score, puzzle.opponent)
            self.assertTrue(check_answer(puzzle, report.recommended)[0])
            for count in set(range(11)) - set(report.best_choices):
                self.assertFalse(check_answer(puzzle, count)[0])

    def test_invalid_positions_and_choices_rejected(self):
        coach_position(1, 1)  # A warm integer cache must not accept True or 1.0.
        for scores in ((100, 0), (-1, 0), (True, 1), (1.0, 1), ([], 1), (1, '2')):
            with self.assertRaises(ValueError): coach_position(*scores)
        for count in (-1, 11, True, '5'):
            with self.assertRaises(ValueError): check_answer(puzzles()[0], count)

    def test_explanation_distinguishes_objectives_and_assumptions(self):
        text = explain_choice(coach_position(37, 81), 5)
        for expected in ('Expected immediate gain', 'Pre-roll gap', 'ZERO-DICE OPTION',
                         'optimal play by both players', 'cannot predict the next roll'):
            self.assertIn(expected, text)

    def test_review_uses_each_players_pre_roll_position(self):
        _, _, events, record = example()
        rows = review_match(record)
        self.assertEqual(len(rows), len(events))
        for row, event in zip(rows, events):
            self.assertEqual((row.position.score, row.position.opponent), (event.score_before, event.opponent_score))
            self.assertGreaterEqual(row.gap, 0)
            self.assertLessEqual(row.gap, 1)
            if event.num_rolls in row.position.best_choices:
                self.assertEqual(row.assessment, 'Model-best')

    def test_dice_luck_does_not_change_pre_roll_decision_value(self):
        first, second = coach_position(0, 0), coach_position(0, 0)
        self.assertEqual(first, second)
        # Two possible outcomes of the same chosen action have equal evaluation.
        lucky = TurnEvent(1, 0, 1, (6,), 0, 0, 6, 7)
        unlucky = TurnEvent(1, 0, 1, (1,), 0, 0, 1, 1)
        self.assertEqual(coach_position(lucky.score_before, lucky.opponent_score).moves[1],
                         coach_position(unlucky.score_before, unlucky.opponent_score).moves[1])

    def test_review_is_read_only_and_rejects_inconsistent_record(self):
        _, _, _, record = example()
        before = deepcopy(record)
        review_match(record)
        self.assertEqual(record, before)
        record['events'][0]['score_after'] += 1
        with self.assertRaises(ValueError): review_match(record)


class CoachDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if tk is None: raise unittest.SkipTest('Tk not installed')
        try:
            root = tk.Tk();root.destroy()
        except tk.TclError:
            raise unittest.SkipTest('Graphical display required')

    def setUp(self):
        self.root = tk.Tk()
        self.errors = []
        self.root.report_callback_exception = lambda kind, error, trace: self.errors.append(error)
        self.app = HogApp(self.root, cpu_delay=600000, preferences=Preferences(animations=False))
        self.root.update()

    def tearDown(self):
        self.app.close()
        self.assertEqual(self.errors, [])

    def wait_ready(self):
        # Use Tk timers rather than sleeping, so worker callbacks are exercised.
        def check():
            if self.app.analysis_pending is None:
                self.root.quit()
            else:
                self.root.after(10, check)
        self.root.after(10, check)
        limit = self.root.after(5000, self.root.quit)
        self.root.mainloop()
        self.root.after_cancel(limit)
        self.assertIsNone(self.app.analysis_pending)
        self.assertEqual(self.errors, [])

    def store_example(self):
        config, session, events, record = example()
        self.app.store.record_match('coach-test', config, session, events)
        return record

    def test_live_coach_snapshot_does_not_play_or_change_choice(self):
        self.app.start_match(MatchConfig(2, ('Alice', 'Bob'), seed=42))
        self.app.select_count(7)
        rng = self.app.session.dice.rng.getstate()
        self.app.show_advice()
        self.wait_ready()
        self.assertEqual(len(self.app.coach_table.get_children()), 11)
        self.assertEqual(self.app.selected_count, 7)
        self.app.coach_table.selection_set('0')
        self.root.update()
        self.assertEqual(self.app.coach_chosen, 0)
        self.assertIn('ZERO-DICE OPTION', self.app.coach_explanation.get('1.0', 'end'))
        self.assertEqual(self.app.selected_count, 7)
        self.assertEqual(self.app.session.dice.rng.getstate(), rng)
        self.assertEqual(self.app.events, [])

    def test_review_seat_filter_sort_and_recorded_explanation(self):
        record = self.store_example()
        self.app.show_review('coach-test')
        self.wait_ready()
        self.assertTrue(all(row.event.player == 0 for row in self.app.review_filtered))
        self.app.review_seat.set('All seats')
        self.app.review_refresh()
        gaps = [row.gap for row in self.app.review_filtered]
        self.assertEqual(gaps, sorted(gaps, reverse=True))
        self.app.review_order.set('Turn order')
        self.app.review_refresh()
        self.assertEqual([row.event.number for row in self.app.review_filtered], list(range(1, len(record['events']) + 1)))
        self.assertIn('RECORDED OUTCOME', self.app.review_explanation.get('1.0', 'end'))
        self.assertEqual(len(self.app.store.history()), 1)

    def test_wrong_puzzle_answer_can_retry_without_spoiler(self):
        self.app.show_puzzles()
        self.wait_ready()
        bad = next(count for count in range(11) if count not in self.app.puzzle_report.best_choices)
        self.app.puzzle_buttons[bad].invoke()
        self.app.puzzle_submit.invoke()
        state = self.app.puzzle_progress[self.app.current_puzzle.identifier]
        self.assertFalse(state['solved'])
        self.assertFalse(state['revealed'])
        self.assertEqual(state['attempts'], 1)
        self.assertIn('Try again', self.app.analysis_status.cget('text'))
        self.assertNotIn('MODEL-BEST CHOICES', self.app.puzzle_explanation.get('1.0', 'end'))
        best = self.app.puzzle_report.recommended
        self.app.puzzle_buttons[best].invoke()
        self.app.puzzle_submit.invoke()
        self.assertTrue(state['solved'])
        self.assertEqual(state['attempts'], 2)
        self.assertEqual(self.app.store.history(), [])

    def test_revealed_answer_does_not_count_as_unassisted(self):
        self.app.show_puzzles()
        self.wait_ready()
        self.app.puzzle_reveal.invoke()
        self.app.puzzle_buttons[self.app.puzzle_report.recommended].invoke()
        self.app.puzzle_submit.invoke()
        state = self.app.puzzle_progress[self.app.current_puzzle.identifier]
        self.assertTrue(state['revealed'])
        self.assertFalse(state['solved'])
        self.assertIn('assisted', self.app.analysis_status.cget('text'))

    def test_puzzle_progress_survives_window_reopening_for_session(self):
        self.app.show_puzzles()
        self.wait_ready()
        self.app.puzzle_buttons[self.app.puzzle_report.recommended].invoke()
        self.app.puzzle_submit.invoke()
        self.app.close_analysis()
        self.app.show_puzzles()
        self.wait_ready()
        self.assertIn('1/8 solved unassisted', self.app.puzzle_progress_label.cget('text'))
        self.app.puzzle_next.invoke()
        self.wait_ready()
        self.assertEqual(self.app.current_puzzle.identifier, 'prime-finish')

    def test_closing_pending_coach_cancels_poll(self):
        self.app.start_match(MatchConfig(2, ('Alice', 'Bob'), seed=42))
        self.app.show_coach()
        self.app.close_analysis()
        self.assertIsNone(self.app.analysis_pending)
        self.assertIsNone(self.app._redraw_insights)
        self.root.update()

    def test_review_and_puzzles_preserve_saved_match_and_rng(self):
        self.store_example()
        self.app.start_match(MatchConfig(2, ('Alice', 'Bob'), seed=91))
        self.app.save_current()
        rng = self.app.session.dice.rng.getstate()
        saved = self.app.store.connection.execute('SELECT payload FROM saves').fetchone()[0]
        before = self.app.store.history()
        for view in (self.app.show_review, self.app.show_puzzles):
            view();self.wait_ready()
            self.app.set_theme('contrast');self.root.update()
            self.app.set_theme('light');self.root.update()
            self.app.close_analysis()
        self.assertEqual(self.app.session.dice.rng.getstate(), rng)
        self.assertEqual(self.app.store.history(), before)
        self.assertEqual(self.app.store.connection.execute('SELECT payload FROM saves').fetchone()[0], saved)

    def test_new_learning_controls_fit_minimum_popup(self):
        self.store_example()
        self.app.start_match(MatchConfig(2, ('Alice', 'Bob'), seed=42))
        for view in (self.app.show_coach, self.app.show_review, self.app.show_puzzles):
            view()
            self.wait_ready()
            window = self.app.analysis_window
            window.geometry('900x720')
            self.root.update()
            if view == self.app.show_coach:
                targets = (self.app.coach_choice_status,)
            elif view == self.app.show_review:
                targets = (self.app.review_selected_status,)
            else:
                targets = (self.app.puzzle_submit, self.app.puzzle_next, self.app.puzzle_progress_label)
            for target in targets:
                self.assertTrue(target.winfo_ismapped())
                self.assertLessEqual(target.winfo_rooty() + target.winfo_height(), window.winfo_rooty() + window.winfo_height())
            self.app.close_analysis()

    def test_match_selectors_distinguish_identical_labels_and_id_prefixes(self):
        expected = json.loads(json.dumps(self.store_example()))
        config, session, events, _ = example(43)
        self.app.store.record_match('coach-second', config, session, events)
        with self.app.store.connection:
            self.app.store.connection.execute("UPDATE matches SET finished_at='2026-10-29T00:00:00+00:00'")
        self.app.show_review()
        self.wait_ready()
        self.assertEqual(len(set(self.app.review_labels)), 2)
        self.app.review_match_var.set(self.app.review_labels[1])
        self.app.review_load()
        self.wait_ready()
        self.assertEqual(self.app.review_record['events'], expected['events'])
        self.app.show_replay()
        self.root.update()
        self.assertEqual(len(set(self.app.replay_labels)), 2)
        self.app.replay_selection.set(self.app.replay_labels[1])
        self.app.replay_load()
        self.assertEqual(self.app.replay_record['events'], expected['events'])

    def test_empty_review_and_hub_fit_minimum_popup(self):
        self.app.show_review()
        self.root.update()
        self.assertIsNone(self.app.analysis_pending)
        self.app.show_coaching_hub()
        self.app.analysis_window.geometry('900x720')
        self.root.update()
        self.assertTrue(self.app.analysis_window.winfo_ismapped())
