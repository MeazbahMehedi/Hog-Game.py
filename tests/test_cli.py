"""Exercise real command-line entry points and interactive input flows."""

import argparse
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import hog_ui

ROOT = Path(__file__).resolve().parents[1]


def run_cli(script, *args, text=""):
    return subprocess.run([sys.executable, str(ROOT / script), *args],
                          input=text, capture_output=True, text=True, cwd=ROOT, timeout=20)


class InputTests(unittest.TestCase):
    def test_bad_inputs_retry_without_crashing(self):
        # Superscript two used to pass isnumeric() and crash int().
        with patch("builtins.input", side_effect=["abc", "\u00b2", "-1", "11", " 3 "]), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(hog_ui.get_int("", 0, 10), 3)

    def test_q_leaves_current_screen(self):
        with patch("builtins.input", return_value="q"):
            with self.assertRaises(hog_ui.BackToMenu):
                hog_ui.get_int("", 0, 10)

    def test_names_reject_control_characters(self):
        for value in ("", "x" * 21, "a\x1b[0m", "a\nb"):
            with self.assertRaises(argparse.ArgumentTypeError):
                hog_ui.valid_name(value)


class CommandLineTests(unittest.TestCase):
    def test_menu_and_exit(self):
        result = run_cli("hog_ui.py", text="0\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("TERMINAL EDITION", result.stdout)
        self.assertIn("Thanks for playing", result.stdout)

    def test_seeded_computer_game_and_flags(self):
        args = ("-n", "0", "--strategy0", "adaptive", "--strategy1", "sus",
                "--name0", "Alice", "--name1", "Bob", "--seed", "42", "--no-replay")
        first = run_cli("hog_ui.py", *args)
        second = run_cli("hog_ui.py", *args)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertIn("MATCH COMPLETE", first.stdout)
        self.assertIn("Alice 107 : 32 Bob", first.stdout)

    def test_human_vs_computer_finishes(self):
        result = run_cli("hog_ui.py", "-n", "1", "--seed", "3", "--no-replay",
                         text="0\n" * 300)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Zero dice guarantees", result.stdout)
        self.assertIn("MATCH COMPLETE", result.stdout)

    def test_two_humans_finish(self):
        result = run_cli("hog_ui.py", "-n", "2", "--no-replay", text="0\n" * 300)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("MATCH COMPLETE", result.stdout)

    def test_menu_setup_names_strategies_and_replay(self):
        # Observe mode, names, adaptive vs sus, replay once, finish, exit menu.
        result = run_cli("hog_ui.py", "--seed", "42", text="3\nAlice\nBob\n6\n5\n1\n0\n0\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("H O G / MATCH COMPLETE"), 2)
        self.assertIn("Alice vs Bob", result.stdout)

    def test_quit_mid_game_returns_to_menu(self):
        result = run_cli("hog_ui.py", text="1\nAlice\nBob\n1\nq\n0\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Returned from the current screen", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_eof_is_a_clean_exit(self):
        result = run_cli("hog_ui.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Input ended", result.stdout)

    def test_experiments_flag_runs_real_measurements(self):
        args = ("-r", "--games", "4", "--samples", "20", "--seed", "42")
        first = run_cli("hog.py", *args)
        second = run_cli("hog.py", *args)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertIn("STRATEGY COMPARISON", first.stdout)
        self.assertIn("8 per strategy", first.stdout)
        self.assertIn("95% interval", first.stdout)
        self.assertEqual(first.stdout, second.stdout)

    def test_invalid_cli_values_exit_with_usage(self):
        cases = [("hog_ui.py", "-n", "3"), ("hog_ui.py", "--no-replay"),
                 ("hog_ui.py", "--strategy1", "unknown"),
                 ("hog.py", "-r", "--games", "0"),
                 ("hog.py", "-r", "--samples", "-1")]
        for script, *args in cases:
            result = run_cli(script, *args)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_version(self):
        for script in ("hog.py", "hog_ui.py", "hog_experiments.py"):
            result = run_cli(script, "--version")
            self.assertEqual(result.stdout.strip(), "1.2.0")


if __name__ == "__main__":
    unittest.main()
