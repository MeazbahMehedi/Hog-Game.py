"""Local SQLite profiles, validated saves, deduplicated history and exports.

No accounts, passwords, network, pickle, or executable deserialization.
"""

import csv
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from random import Random
import sqlite3
from uuid import uuid4

from hog import GameSession, TurnEvent, seeded_dice, sus_update
from hog_match import MatchConfig
from hog_campaign_storage import CampaignStorage


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_snapshot(config, session, events, match_id):
    if session.finished:
        raise ValueError("Only unfinished matches can be saved.")
    return {"schema": 1, "match_id": match_id, "config": asdict(config),
            "events": [asdict(event) for event in events],
            "rng_state": session.dice.rng.getstate()}


def restore_snapshot(payload):
    """Replay recorded outcomes to validate scores before restoring RNG state."""
    if not isinstance(payload, dict) or payload.get("schema") != 1:
        raise ValueError("Unsupported saved-game format.")
    match_id = payload.get("match_id")
    if not isinstance(match_id, str) or len(match_id) != 32:
        raise ValueError("Invalid saved match identity.")
    raw = payload.get("config")
    if not isinstance(raw, dict):
        raise ValueError("Invalid match configuration.")
    try:
        config = MatchConfig(raw["num_players"], tuple(raw["names"]),
                             tuple(raw["strategies"]), raw["seed"],
                             tuple(raw.get("profile_ids", (None, None))))
        session = GameSession(dice=seeded_dice(config.seed))
        events = []
        data = payload["events"]
        if not isinstance(data, list) or len(data) > 200:
            raise ValueError("Invalid saved turn history.")
        for raw_event in data:
            event = TurnEvent(**{**raw_event, "outcomes": tuple(raw_event["outcomes"])})
            if (type(event.num_rolls) is not int or not 0 <= event.num_rolls <= 10
                    or len(event.outcomes) != event.num_rolls
                    or any(type(value) is not int or not 1 <= value <= 6 for value in event.outcomes)):
                raise ValueError("Invalid dice outcomes.")
            outcomes = iter(event.outcomes)
            session.dice = lambda: next(outcomes)
            actual = session.advance(event.num_rolls)
            if actual != event:
                raise ValueError("Saved scoring does not match the Hog rules.")
            events.append(actual)
        if session.finished:
            raise ValueError("The saved match has already finished.")
        state = payload["rng_state"]
        if (not isinstance(state, (list, tuple)) or len(state) != 3
                or state[0] != 3 or not isinstance(state[1], (list, tuple))
                or len(state[1]) != 625 or state[2] is not None
                or any(type(value) is not int for value in state[1])
                or any(not 0 <= value <= 0xFFFFFFFF for value in state[1][:-1])
                or not 0 <= state[1][-1] <= 624):
            raise ValueError("Invalid saved dice state.")
        dice = seeded_dice()
        dice.rng.setstate((3, tuple(state[1]), None))
        session.dice = dice
        return config, session, events, match_id
    except (KeyError, TypeError, StopIteration, OverflowError) as error:
        raise ValueError("Invalid saved-game data.") from error


class Store(CampaignStorage):
    def __init__(self, path=None, *, check_same_thread=True):
        if path is not None:
            path = Path(path)
            path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path) if path is not None else ":memory:", check_same_thread=check_same_thread)
        version = self.connection.execute("PRAGMA user_version").fetchone()[0]
        if version > 3:
            self.connection.close()
            raise sqlite3.DatabaseError("This database was created by a newer Hog version.")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        try:
            if version in (1, 2) and path is not None:
                backup = Path(str(path) + f".v{version}-backup")
                if not backup.exists():
                    temporary = Path(str(backup) + "." + uuid4().hex)
                    try:
                        target = sqlite3.connect(temporary)
                        try:
                            self.connection.backup(target)
                        finally:
                            target.close()
                        temporary.replace(backup)
                    finally:
                        temporary.unlink(missing_ok=True)
            self.connection.executescript("""
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS profiles(
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, name_key TEXT UNIQUE NOT NULL,
                    created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS matches(
                    id TEXT PRIMARY KEY, finished_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS players(
                    match_id TEXT REFERENCES matches(id), seat INTEGER, profile_id TEXT REFERENCES profiles(id),
                    name TEXT, score INTEGER, won INTEGER, turns INTEGER, zeros INTEGER,
                    bonuses INTEGER, sow INTEGER, PRIMARY KEY(match_id, seat));
                CREATE TABLE IF NOT EXISTS saves(slot INTEGER PRIMARY KEY, updated_at TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS tournaments(id TEXT PRIMARY KEY, created_at TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS campaign_runs(
                    id TEXT PRIMARY KEY, profile_id TEXT NOT NULL REFERENCES profiles(id),
                    stage_id TEXT NOT NULL, finished_at TEXT NOT NULL,
                    stars INTEGER NOT NULL CHECK(stars BETWEEN 0 AND 3),
                    cleared INTEGER NOT NULL CHECK(cleared IN (0,1)), payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS profile_cosmetics(
                    profile_id TEXT PRIMARY KEY REFERENCES profiles(id),
                    dice TEXT NOT NULL, avatar TEXT NOT NULL, theme TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS profile_archive(
                    profile_id TEXT PRIMARY KEY REFERENCES profiles(id));
                PRAGMA user_version = 3;
                COMMIT;
            """)
        except (OSError, sqlite3.Error):
            self.connection.rollback()
            self.connection.close()
            raise

    def close(self):
        self.connection.close()

    def create_profile(self, name):
        name = name.strip()
        if not name or len(name) > 20 or not all(char.isprintable() for char in name):
            raise ValueError("Use a name of 1-20 printable characters.")
        if name.casefold() == "guest / no profile":
            raise ValueError("That name is reserved for guest play.")
        identifier = uuid4().hex
        try:
            with self.connection:
                self.connection.execute("INSERT INTO profiles VALUES(?,?,?,?)",
                                        (identifier, name, name.casefold(), timestamp()))
        except sqlite3.IntegrityError as error:
            raise ValueError("That profile name already exists.") from error
        return identifier

    def profiles(self, include_archived=False):
        sql = "SELECT p.*, (a.profile_id IS NOT NULL) AS archived FROM profiles p LEFT JOIN profile_archive a ON a.profile_id=p.id"
        if not include_archived:
            sql += " WHERE a.profile_id IS NULL"
        return [dict(row) for row in self.connection.execute(sql + " ORDER BY name_key")]

    def rename_profile(self, identifier, name):
        self._campaign_profile(identifier)
        # Reuse exactly the same name validation as profile creation.
        name = name.strip()
        if (not name or len(name) > 20 or not all(c.isprintable() for c in name)
                or name.casefold() == "guest / no profile"):
            raise ValueError("Use a name of 1-20 printable characters; the guest name is reserved.")
        try:
            with self.connection:
                self.connection.execute("UPDATE profiles SET name=?, name_key=? WHERE id=?",
                                        (name, name.casefold(), identifier))
        except sqlite3.IntegrityError as error:
            raise ValueError("That profile name already exists.") from error

    def archive_profile(self, identifier, archived=True):
        self._campaign_profile(identifier)
        if type(archived) is not bool:
            raise ValueError("Archive status must be true or false.")
        with self.connection:
            if archived:
                self.connection.execute("INSERT OR IGNORE INTO profile_archive VALUES(?)", (identifier,))
            else:
                self.connection.execute("DELETE FROM profile_archive WHERE profile_id=?", (identifier,))

    def stats(self):
        rows = self.connection.execute("""
            SELECT p.id, p.name, COUNT(x.match_id) AS played, COALESCE(SUM(x.won),0) AS wins,
            COALESCE(SUM(x.zeros),0) AS zero_turns, COALESCE(SUM(x.bonuses),0) AS bonuses,
            COALESCE(MAX(x.score),0) AS best_score
            FROM profiles p LEFT JOIN players x ON p.id=x.profile_id
            GROUP BY p.id ORDER BY wins DESC, played DESC, p.name_key
        """)
        return [dict(row) for row in rows]

    def achievements(self, identifier):
        stats = next((row for row in self.stats() if row["id"] == identifier), None)
        if stats is None:
            raise ValueError("Unknown profile.")
        conditions = (("First finish", stats["played"] >= 1), ("First victory", stats["wins"] >= 1),
                      ("Five victories", stats["wins"] >= 5), ("Ten matches", stats["played"] >= 10),
                      ("Free points", stats["zero_turns"] >= 1), ("Prime time", stats["bonuses"] >= 1))
        return [(name, bool(unlocked)) for name, unlocked in conditions]

    def record_match(self, match_id, config, session, events):
        if not session.finished:
            raise ValueError("An unfinished match cannot enter history.")
        record = {"config": asdict(config), "scores": session.scores,
                  "events": [asdict(event) for event in events]}
        with self.connection:
            cursor = self.connection.execute("INSERT OR IGNORE INTO matches VALUES(?,?,?)",
                                             (match_id, timestamp(), json.dumps(record)))
            if not cursor.rowcount:
                return False
            for seat in (0, 1):
                turns = [event for event in events if event.player == seat]
                self.connection.execute("INSERT INTO players VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (match_id, seat, config.profile_ids[seat], config.names[seat], session.scores[seat],
                     int(session.winner == seat), len(turns), sum(event.num_rolls == 0 for event in turns),
                     sum(event.bonus > 0 for event in turns), sum(1 in event.outcomes for event in turns)))
            saved = self.connection.execute("SELECT payload FROM saves WHERE slot=1").fetchone()
            if saved:
                try:
                    payload = json.loads(saved[0])
                except (ValueError, TypeError):
                    payload = None
                if isinstance(payload, dict) and payload.get("match_id") == match_id:
                    self.connection.execute("DELETE FROM saves WHERE slot=1")
        return True

    def history(self):
        return [dict(row) for row in self.connection.execute("SELECT * FROM matches ORDER BY finished_at DESC, rowid DESC")]

    def save(self, config, session, events, match_id):
        payload = make_snapshot(config, session, events, match_id)
        with self.connection:
            self.connection.execute("INSERT OR REPLACE INTO saves VALUES(1,?,?)",
                                    (timestamp(), json.dumps(payload)))

    def load(self):
        row = self.connection.execute("SELECT payload FROM saves WHERE slot=1").fetchone()
        if row is None:
            raise ValueError("No saved match is available.")
        try:
            return restore_snapshot(json.loads(row[0]))
        except (json.JSONDecodeError, TypeError) as error:
            raise ValueError("The saved match could not be read.") from error

    def save_tournament(self, result):
        identifier = uuid4().hex
        with self.connection:
            self.connection.execute("INSERT INTO tournaments VALUES(?,?,?)",
                                    (identifier, timestamp(), json.dumps(result)))
        return identifier

    def tournaments(self):
        return [dict(row) for row in self.connection.execute("SELECT * FROM tournaments ORDER BY rowid DESC")]

    def export_history(self, path):
        rows = self.connection.execute("""SELECT m.finished_at, x.match_id, x.seat, x.name,
            x.score, x.won, x.turns, x.zeros, x.bonuses, x.sow
            FROM players x JOIN matches m ON m.id=x.match_id ORDER BY m.finished_at, x.seat""").fetchall()
        with open(path, "w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.writer(stream)
            writer.writerow(("finished_at", "match_id", "seat", "name", "score", "won", "turns", "zero_dice", "sus_fuss", "sow_sad"))
            for row in rows:
                writer.writerow(["'" + value if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@"))
                                 else value for value in row])
