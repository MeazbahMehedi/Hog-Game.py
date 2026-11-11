"""Transactional campaign attempts and profile cosmetics on the main Tk thread."""

from dataclasses import asdict
import json
from uuid import uuid4

from hog import GameSession, TurnEvent, seeded_dice
from hog_campaign import (stage_by_id, available_stages, earned_cosmetics, cosmetics,
                          evaluate_stage)


class CampaignStorage:
    def _campaign_profile(self, identifier):
        row = self.connection.execute('SELECT name FROM profiles WHERE id=?', (identifier,)).fetchone()
        if row is None:
            raise ValueError('Choose an existing local profile.')
        return row[0]

    def campaign_progress(self, identifier):
        self._campaign_profile(identifier)
        rows = self.connection.execute('''SELECT stage_id, COUNT(*) AS attempts,
            MAX(stars) AS stars, MAX(cleared) AS cleared FROM campaign_runs
            WHERE profile_id=? GROUP BY stage_id''', (identifier,))
        return {row['stage_id']: {'attempts': row['attempts'], 'stars': row['stars'],
                                 'cleared': bool(row['cleared'])} for row in rows}

    def record_campaign(self, run_id, identifier, stage_id, events):
        """Validate the fixed seeded run, then insert it once, atomically."""
        from hog_storage import timestamp
        from hog_match import MatchConfig
        name = self._campaign_profile(identifier)
        stage = stage_by_id(stage_id)
        if not isinstance(run_id, str) or len(run_id) != 32:
            raise ValueError('Invalid campaign run identity.')
        if not isinstance(events, (tuple, list)) or not 1 <= len(events) <= 200:
            raise ValueError('Invalid campaign turn history.')
        session = GameSession(dice=seeded_dice(stage.seed))
        for event in events:
            if not isinstance(event, TurnEvent):
                raise ValueError("Invalid campaign event.")
            if session.current_player == 1:
                from hog import STRATEGIES
                expected = STRATEGIES[stage.strategy][0](session.scores[1], session.scores[0])
                if event.num_rolls != expected:
                    raise ValueError('Campaign opponent decisions do not match this stage.')
            if session.advance(event.num_rolls) != event:
                raise ValueError('Campaign turns do not match the fixed stage seed and rules.')
        config = MatchConfig(1, (name, stage.opponent), ('always5', stage.strategy), stage.seed, (identifier, None))
        record = {'config': asdict(config), 'scores': session.scores,
                  'events': [asdict(event) for event in events]}
        result = evaluate_stage(stage, record)
        with self.connection:
            if self.connection.execute('SELECT 1 FROM campaign_runs WHERE id=?', (run_id,)).fetchone():
                return False
            if stage_id not in available_stages(self.campaign_progress(identifier)):
                raise ValueError('Clear the previous campaign stage first.')
            self.connection.execute('INSERT INTO campaign_runs VALUES(?,?,?,?,?,?,?)',
                (run_id, identifier, stage_id, timestamp(), result['stars'], int(result['cleared']), json.dumps(record)))
        return True

    def campaign_runs(self, identifier):
        self._campaign_profile(identifier)
        return [dict(row) for row in self.connection.execute(
            'SELECT * FROM campaign_runs WHERE profile_id=? ORDER BY rowid DESC', (identifier,))]

    def equipment(self, identifier):
        defaults = {'dice': 'classic', 'avatar': 'initials', 'theme': 'dark'}
        if identifier is None:
            return defaults
        self._campaign_profile(identifier)
        row = self.connection.execute('SELECT dice,avatar,theme FROM profile_cosmetics WHERE profile_id=?', (identifier,)).fetchone()
        if row:
            known = {(item.kind, item.identifier) for item in cosmetics()}
            defaults.update({kind: value for kind, value in dict(row).items() if (kind, value) in known})
        return defaults

    def equip_cosmetic(self, identifier, kind, value):
        self._campaign_profile(identifier)
        if kind not in ('dice', 'avatar', 'theme'):
            raise ValueError('Unknown cosmetic type.')
        if (kind, value) not in {(item.kind, item.identifier) for item in cosmetics()}:
            raise ValueError('Unknown cosmetic.')
        if (kind, value) not in {(item.kind, item.identifier) for item in earned_cosmetics(self.campaign_progress(identifier))}:
            raise ValueError('Earn more campaign stars to unlock this cosmetic.')
        equipment = self.equipment(identifier)
        equipment[kind] = value
        with self.connection:
            self.connection.execute('INSERT OR REPLACE INTO profile_cosmetics VALUES(?,?,?,?)',
                                    (identifier, equipment['dice'], equipment['avatar'], equipment['theme']))
