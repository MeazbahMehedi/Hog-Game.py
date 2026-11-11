"""Portable JSON backups rebuilt through the game's validators before restore.

No SQLite files, SQL, pickle, executable objects or archive extraction are read.
The checksum detects accidental damage; it is not an authenticity signature.
"""

from dataclasses import asdict, dataclass, fields
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import tempfile

from hog import GameSession, TurnEvent, VERSION
from hog_match import MatchConfig
from hog_preferences import Preferences
from hog_statistics import read_matches
from hog_storage import Store, restore_snapshot, timestamp
from hog import STRATEGIES

MAX_BYTES = 32 * 1024 * 1024
TABLES = ('profiles', 'matches', 'saves', 'tournaments', 'campaign_runs',
          'profile_cosmetics', 'profile_archive')


def _encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def export_backup(path, store, preferences):
    # Hold one read snapshot even if another Hog process uses the same database.
    connection = store.connection
    connection.execute('SAVEPOINT hog_portable_export')
    try:
        tables = {table: [dict(row) for row in connection.execute(f'SELECT * FROM {table} ORDER BY rowid')]
                  for table in TABLES}
    finally:
        connection.execute('RELEASE SAVEPOINT hog_portable_export')
    body = {'format': 'hog-backup', 'schema': 1, 'game_version': VERSION,
            'created_at': timestamp(), 'preferences': asdict(preferences), 'tables': tables}
    encoded = _encoded({'body': body, 'sha256': hashlib.sha256(_encoded(body)).hexdigest()})
    if len(encoded) + 1 > MAX_BYTES:
        raise ValueError('This backup exceeds the 32 MiB portable-backup limit.')
    _atomic_write(path, encoded + b'\n')


def _identity(value):
    if type(value) is not str or len(value) != 32 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('Invalid backup record identity.')
    return value


def _date(value):
    if not isinstance(value, str) or len(value) > 50:
        raise ValueError('Invalid backup date.')
    if datetime.fromisoformat(value).tzinfo is None:
        raise ValueError('Backup dates must include a timezone.')
    return value


def _config(raw):
    return MatchConfig(raw['num_players'], tuple(raw['names']), tuple(raw['strategies']),
                       raw['seed'], tuple(raw.get('profile_ids', (None, None))))


def _events(record):
    return [TurnEvent(**{**row, 'outcomes': tuple(row['outcomes'])}) for row in record['events']]


def _tournament(result):
    keys, games, matches = result['strategies'], result['games_per_seat'], result['matches']
    if (result['schema'] != 1 or type(result['seed']) is not int or type(games) is not int
            or not 1 <= games <= 200 or not isinstance(keys, list) or not 2 <= len(keys) <= 9
            or len(set(keys)) != len(keys) or any(key not in STRATEGIES for key in keys)
            or not isinstance(matches, list) or len(matches) != len(keys) * (len(keys)-1) * games):
        raise ValueError('Invalid saved tournament.')
    counts = {(a, b): 0 for a in keys for b in keys if a != b}
    table = {key: dict(strategy=key, played=0, wins=0, points_for=0, points_against=0) for key in keys}
    for row in matches:
        a, b, x, y = row['first'], row['second'], row['score0'], row['score1']
        if ((a, b) not in counts or type(x) is not int or type(y) is not int
                or not 0 <= min(x, y) < 100 <= max(x, y) <= 163
                or row['winner'] != (a if x > y else b)):
            raise ValueError('Invalid tournament result.')
        counts[a, b] += 1
        for key, own, other in ((a, x, y), (b, y, x)):
            item = table[key]
            item['played'] += 1
            item['wins'] += int(own > other)
            item['points_for'] += own
            item['points_against'] += other
    standings = sorted(table.values(), key=lambda r: (-r['wins'], -(r['points_for']-r['points_against']), r['strategy']))
    if any(count != games for count in counts.values()) or result['standings'] != standings:
        raise ValueError('Tournament standings do not match its results.')


@dataclass
class PreparedBackup:
    store: Store
    preferences: Preferences
    created_at: str
    version: str

    @property
    def counts(self):
        return {table: self.store.connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                for table in TABLES}

    def close(self):
        self.store.close()


def prepare_backup(path):
    """Read bounded JSON and rebuild an isolated database; never alter live data."""
    candidate = None
    try:
        with Path(path).open('rb') as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError('Backup exceeds 32 MiB.')
        package = json.loads(data)
        body = package['body']
        if package['sha256'] != hashlib.sha256(_encoded(body)).hexdigest():
            raise ValueError('Backup checksum mismatch; the file may be damaged.')
        if body['format'] != 'hog-backup' or type(body['schema']) is not int or body['schema'] != 1:
            raise ValueError('Unsupported backup format.')
        raw_preferences = body['preferences']
        if set(raw_preferences) != {field.name for field in fields(Preferences)}:
            raise ValueError('Unsupported backup preferences.')
        preferences = Preferences(**raw_preferences)
        tables = body['tables']
        if set(tables) != set(TABLES) or any(not isinstance(rows, list) or len(rows) > 10000 for rows in tables.values()):
            raise ValueError('Invalid backup tables or record limit exceeded (10,000 per table).')
        for table, rows in tables.items():
            key = 'profile_id' if table in ('profile_archive', 'profile_cosmetics') else 'slot' if table == 'saves' else 'id'
            identities = [row[key] for row in rows]
            if len(set(identities)) != len(identities):
                raise ValueError('Duplicate backup record identities.')
        # This isolated connection is handed to the Tk thread only AFTER the
        # validation future completes. It is never accessed concurrently.
        candidate = Store(check_same_thread=False)
        for row in tables['profiles']:
            identifier = _identity(row['id'])
            generated = candidate.create_profile(row['name'])
            if row['name_key'] != row['name'].casefold():
                raise ValueError('Invalid profile name key.')
            with candidate.connection:
                candidate.connection.execute('UPDATE profiles SET id=?, created_at=? WHERE id=?',
                                             (identifier, _date(row['created_at']), generated))
        matches, skipped = read_matches(tables['matches'])
        if skipped or len(matches) != len(tables['matches']):
            raise ValueError('A completed match is invalid or duplicated.')
        for match in matches:
            _identity(match.identifier)
            session = GameSession()
            events = _events(match.record)
            for event in events:
                outcomes = iter(event.outcomes)
                session.dice = lambda: next(outcomes)
                session.advance(event.num_rolls)
            candidate.record_match(match.identifier, match.config, session, events)
            with candidate.connection:
                candidate.connection.execute('UPDATE matches SET finished_at=? WHERE id=?',
                                             (_date(match.finished_at), match.identifier))
        if len(tables['saves']) > 1:
            raise ValueError('Only one manual save is supported.')
        for row in tables['saves']:
            if type(row['slot']) is not int or row['slot'] != 1:
                raise ValueError('Invalid save slot.')
            config, session, events, identifier = restore_snapshot(json.loads(row['payload']))
            _identity(identifier)
            known = {row['id'] for row in candidate.profiles(True)}
            if any(value is not None and value not in known for value in config.profile_ids):
                raise ValueError('Saved game refers to a missing profile.')
            candidate.save(config, session, events, identifier)
            with candidate.connection:
                candidate.connection.execute('UPDATE saves SET updated_at=?', (_date(row['updated_at']),))
        for row in tables['campaign_runs']:
            identifier = _identity(row['id'])
            record = json.loads(row['payload'])
            config = _config(record['config'])
            if config.profile_ids != (row['profile_id'], None):
                raise ValueError('Campaign profile mismatch.')
            candidate.record_campaign(identifier, row['profile_id'], row['stage_id'], _events(record))
            saved = candidate.connection.execute('SELECT * FROM campaign_runs WHERE id=?', (identifier,)).fetchone()
            canonical = json.loads(saved['payload'])
            if (type(row['stars']) is not int or type(row['cleared']) is not int
                    or row['stars'] != saved['stars'] or row['cleared'] != saved['cleared']
                    or record['scores'] != canonical['scores']
                    or config.num_players != 1 or config.names[1] != canonical['config']['names'][1]
                    or config.seed != canonical['config']['seed'] or config.strategies != tuple(canonical['config']['strategies'])):
                raise ValueError('Campaign rewards do not match the recorded run.')
            with candidate.connection:
                candidate.connection.execute('UPDATE campaign_runs SET finished_at=?,payload=? WHERE id=?',
                                             (_date(row['finished_at']), json.dumps(record), identifier))
        for row in tables['profile_cosmetics']:
            for kind in ('dice', 'avatar', 'theme'):
                candidate.equip_cosmetic(row['profile_id'], kind, row[kind])
        for row in tables['profile_archive']:
            candidate.archive_profile(row['profile_id'])
        for row in tables['tournaments']:
            identifier = _identity(row['id'])
            result = json.loads(row['payload'])
            _tournament(result)
            with candidate.connection:
                candidate.connection.execute('INSERT INTO tournaments VALUES(?,?,?)',
                                             (identifier, _date(row['created_at']), json.dumps(result)))
        if candidate.connection.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Backup contains missing profile references.')
        version = body['game_version']
        if type(version) is not str or len(version) > 30 or not version.isascii() or not all(c.isalnum() or c == '.' for c in version):
            raise ValueError('Invalid game version.')
        return PreparedBackup(candidate, preferences, _date(body['created_at']), version)
    except OSError:
        if candidate: candidate.close()
        raise
    except Exception as error:
        if candidate: candidate.close()
        raise ValueError(f'Backup could not be validated: {error}') from error


def restore_backup(prepared, target, safety_path, current_preferences):
    """Require a successful safety export before SQLite's atomic backup replace."""
    export_backup(safety_path, target, current_preferences)
    prepared.store.connection.backup(target.connection)
    return prepared.preferences


def discard_prepared(future):
    """Dispose abandoned validation results without retaining any Tk object."""
    if not future.cancelled():
        try:
            future.result().close()
        except Exception:
            pass
