"""Read-only statistics and scoring explanations from validated match records.

No simulations, random-number calls, database writes, or policy estimates.
"""

from collections import Counter
from dataclasses import dataclass
import json

from hog_match import MatchConfig
from hog_showcase import replay_states


@dataclass(frozen=True)
class RecordedMatch:
    identifier: str
    finished_at: str
    config: MatchConfig
    record: dict
    states: tuple


def read_matches(rows):
    """Keep the first copy of each ID; reject invalid or incomplete records.

    Input order is preserved (the store supplies newest first). Legacy records
    without profile assignments remain valid and contribute to all-seat totals.
    """
    matches, skipped, seen = [], 0, set()
    for row in rows:
        try:
            identifier = row['id']
            if not isinstance(identifier, str) or not identifier:
                raise ValueError('Missing match identity')
            if identifier in seen:
                continue
            seen.add(identifier)
            record = json.loads(row['payload'])
            raw = record['config']
            config = MatchConfig(raw['num_players'], tuple(raw['names']), tuple(raw['strategies']),
                                 raw['seed'], tuple(raw.get('profile_ids', (None, None))))
            states = replay_states(record)
            matches.append(RecordedMatch(identifier, str(row['finished_at']), config, record, states))
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
            skipped += 1
    return tuple(matches), skipped


def opponent_key(config, seat):
    """Group computers by strategy and humans by persistent identity when known."""
    other = 1 - seat
    if not config.is_human(other):
        return 'cpu:' + config.strategies[other], 'Computer / ' + config.strategies[other]
    identifier = config.profile_ids[other]
    if identifier:
        return 'profile:' + identifier, 'Profile / ' + config.names[other]
    name = config.names[other]
    return 'guest:' + name.casefold(), 'Guest / ' + name


def summarize(matches, profile_id=None):
    """Aggregate selected recorded seats, in chronological order for streaks.

    None means BOTH seats, not a human skill estimate. Per-profile filters use
    profile IDs, so editing a match display name does not split one player.
    """
    dice = Counter({count: 0 for count in range(11)})
    opponents = {}
    appearances = wins = turns = total_gain = sow = zeros = bonuses = 0
    best_score = best_gain = best_bonus = best_margin = streak = best_streak = 0
    match_ids = set()
    for match in reversed(matches):
        config = match.config
        scores = match.states[-1]['scores']
        winner = 0 if scores[0] > scores[1] else 1
        for seat in (0, 1):
            if profile_id is not None and config.profile_ids[seat] != profile_id:
                continue
            events = [state['event'] for state in match.states[1:] if state['event'].player == seat]
            won = seat == winner
            appearances += 1
            wins += won
            match_ids.add(match.identifier)
            best_score = max(best_score, scores[seat])
            if won:
                best_margin = max(best_margin, scores[seat] - scores[1 - seat])
            if profile_id is not None:
                streak = streak + 1 if won else 0
                best_streak = max(best_streak, streak)
            key, name = opponent_key(config, seat)
            row = opponents.setdefault(key, {'key': key, 'name': name, 'played': 0, 'wins': 0})
            row['name'] = name  # Latest recorded display name for this identity.
            row['played'] += 1
            row['wins'] += won
            for event in events:
                dice[event.num_rolls] += 1
                gain = event.score_after - event.score_before
                turns += 1
                total_gain += gain
                best_gain = max(best_gain, gain)
                best_bonus = max(best_bonus, event.bonus)
                sow += 1 in event.outcomes
                zeros += event.num_rolls == 0
                bonuses += event.bonus > 0
    return {'matches': len(match_ids), 'appearances': appearances, 'wins': wins,
            'losses': appearances - wins, 'win_rate': wins / appearances if appearances else None,
            'turns': turns, 'average_gain': total_gain / turns if turns else None,
            'sow': sow, 'zeros': zeros, 'bonuses': bonuses,
            'dice_counts': tuple(dice[count] for count in range(11)),
            'opponents': tuple(sorted(opponents.values(), key=lambda row: (-row['played'], row['name'].casefold()))),
            'best_score': best_score, 'best_gain': best_gain, 'best_bonus': best_bonus,
            'best_margin': best_margin, 'best_streak': best_streak if profile_id is not None else None}


def key_moments(states):
    """Find factual milestones rather than judging whether a move was optimal."""
    if len(states) < 2:
        return ()
    labels = {}

    def mark(number, title):
        labels.setdefault(number, []).append(title)

    events = [state['event'] for state in states[1:]]
    biggest = max(events, key=lambda event: event.score_after - event.score_before)
    mark(biggest.number, 'Largest score gain')
    bonus = max(events, key=lambda event: event.bonus)
    if bonus.bonus:
        mark(bonus.number, 'Largest Sus Fuss bonus')
    # A tie is not a lead change. Remember the last non-tied leader.
    leader = None
    for index, state in enumerate(states[1:], 1):
        scores = state['scores']
        current = None if scores[0] == scores[1] else int(scores[1] > scores[0])
        if current is not None:
            if leader is not None and current != leader:
                mark(index, 'Lead changed')
            leader = current
    mark(len(states) - 1, 'Winning turn')
    return tuple((number, ' / '.join(titles)) for number, titles in sorted(labels.items()))


def explain_turn(state, names):
    event = state['event']
    if event is None:
        return 'Before turn 1. Both players start at zero; Player 0 moves first.'
    if event.num_rolls == 0:
        source = f'Boar Brawl: zero dice earned {event.turn_points} guaranteed points.'
    elif 1 in event.outcomes:
        source = f'Sow Sad: a rolled 1 reduced the base turn to 1 point (dice sum {sum(event.outcomes)}).'
    else:
        source = f'Dice total: the {event.num_rolls} recorded dice sum to {event.turn_points}.'
    ordinary = event.score_before + event.turn_points
    bonus = (f'Sus Fuss raised {ordinary} to {event.score_after}, adding {event.bonus}.' if event.bonus
             else f'No Sus Fuss adjustment; the new score is {event.score_after}.')
    return f'{names[event.player]} / {source}\n{event.score_before} + {event.turn_points} + {event.bonus} = {event.score_after}. {bonus}'
