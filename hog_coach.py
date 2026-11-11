"""Offline decision coaching using the existing exact fair-dice policy.

Reviews evaluate the position BEFORE each recorded roll. Outcomes are shown
separately; they do not change a move's pre-roll model value.
"""

from dataclasses import dataclass
from functools import lru_cache

from hog import boar_brawl, sus_points
from hog_ai import analyze_moves, validate_scores, roll_distribution
from hog_showcase import replay_states

TIE_TOLERANCE = 1e-9
ASSUMPTIONS = ('Standard goal 100; fair six-sided dice; Sow Sad, Boar Brawl and Sus Fuss; '
               'optimal play by both players after the evaluated move. Model chances are not '
               'measured rates against your selected opponent and cannot predict the next roll.')


@dataclass(frozen=True)
class PositionReport:
    score: int
    opponent: int
    moves: tuple
    best_choices: tuple
    finish_chances: tuple

    @property
    def recommended(self):
        return self.best_choices[0]


def coach_position(score, opponent):
    # Validate before caching: bool and float keys can otherwise alias integers.
    validate_scores(score, opponent)
    return _cached_position(score, opponent)


@lru_cache(maxsize=10000)
def _cached_position(score, opponent):
    moves = analyze_moves(score, opponent)
    best = max(move.win_probability for move in moves)
    choices = tuple(move.dice for move in moves if best - move.win_probability <= TIE_TOLERANCE)
    finishes = []
    for count in range(11):
        distribution = ((boar_brawl(score, opponent), 1.0),) if count == 0 else roll_distribution(count)
        finishes.append(sum(weight for points, weight in distribution if sus_points(score + points) >= 100))
    return PositionReport(score, opponent, moves, choices, tuple(finishes))


def action_name(count):
    return '0 dice / Boar Brawl' if count == 0 else f'{count} dice'


def explain_choice(report, chosen):
    if type(chosen) is not int or not 0 <= chosen <= 10:
        raise ValueError('Choose 0-10 dice.')
    played = report.moves[chosen]
    best = report.moves[report.recommended]
    gap = max(0.0, best.win_probability - played.win_probability)
    base = boar_brawl(report.score, report.opponent)
    free = sus_points(report.score + base) - report.score
    greedy = max(move.expected_gain for move in report.moves)
    greedy_choices = [str(move.dice) for move in report.moves if greedy - move.expected_gain <= TIE_TOLERANCE]
    lines = [
        f'POSITION: {report.score} vs {report.opponent}',
        f'MODEL-BEST CHOICES: {", ".join(map(str, report.best_choices))} dice. Lowest tied count is displayed first.',
        '', f'CONSIDERED MOVE: {action_name(chosen)}',
        f'Model win chance: {played.win_probability:.2%}; best available: {best.win_probability:.2%}.',
        f'Pre-roll gap: {gap * 100:.2f} percentage points.',
        f'Expected immediate gain: {played.expected_gain:.2f} points; recommended move: {best.expected_gain:.2f}.',
        f'Sow Sad risk: {played.sow_sad_probability:.1%}; recommended move: {best.sow_sad_probability:.1%}.',
        f'Chance to finish on THIS turn: {report.finish_chances[chosen]:.2%}; recommended move: {report.finish_chances[report.recommended]:.2%}.',
        '', 'WHY THIS RANKING?',
        'The policy compares every possible outcome and the resulting opponent turn. It ranks moves by match-winning probability, not just their average points.',
        f'The largest immediate expected gain is {greedy:.2f} points with {", ".join(greedy_choices)} dice. Maximizing immediate points and maximizing match-winning chance can select different moves.',
        '', 'ZERO-DICE OPTION',
        f'Boar Brawl gives {base} base points here. Sus Fuss adds {free - base}, for a guaranteed gain of {free} and a new score of {report.score + free}.',
    ]
    if report.finish_chances[report.recommended] >= 1 - TIE_TOLERANCE:
        lines.extend(('', 'The recommended move finishes the match for every modeled dice outcome.'))
    elif gap <= TIE_TOLERANCE:
        lines.extend(('', 'This considered move ties the highest model value within numerical tolerance. A later unlucky roll does not change that pre-roll evaluation.'))
    else:
        lines.extend(('', 'The recommended move has the higher pre-roll model value. A good result from this considered move would not remove that decision gap.'))
    if (any(chance >= 1 - TIE_TOLERANCE for chance in report.finish_chances)
            and report.finish_chances[chosen] < 1 - TIE_TOLERANCE):
        lines.extend(('', 'A guaranteed finish was available; this considered move does not guarantee finishing on this turn.'))
    lines.extend(('', 'MODEL ASSUMPTIONS', ASSUMPTIONS))
    return '\n'.join(lines)


@dataclass(frozen=True)
class ReviewedTurn:
    event: object
    position: PositionReport
    gap: float
    assessment: str


def review_match(record):
    states = replay_states(record)
    rows = []
    for state in states[1:]:
        event = state['event']
        report = coach_position(event.score_before, event.opponent_score)
        best = report.moves[report.recommended].win_probability
        gap = max(0.0, best - report.moves[event.num_rolls].win_probability)
        assessment = 'Model-best' if gap <= TIE_TOLERANCE else 'Close' if gap <= .01 else 'Review' if gap <= .05 else 'Large gap'
        rows.append(ReviewedTurn(event, report, gap, assessment))
    return tuple(rows)


@dataclass(frozen=True)
class Puzzle:
    identifier: str
    title: str
    score: int
    opponent: int
    prompt: str


def puzzles():
    # Answers are calculated by the same policy used by the coach, not stored
    # guesses. These positions cover safe finishes, prime promotion and races.
    return (
        Puzzle('safe-finish', 'Take the finish', 98, 90, 'Choose a move with the highest model chance of winning. Check the zero-dice option.'),
        Puzzle('prime-finish', 'A prime opportunity', 14, 60, 'Compare expected gains after Sus Fuss and choose the best model chance.'),
        Puzzle('opening', 'The opening table', 0, 0, 'At the start of a fair match, which dice choice maximizes the model win chance?'),
        Puzzle('behind', 'Chasing the leader', 37, 81, 'You are behind. Choose the model-best action, not necessarily the greatest immediate gain.'),
        Puzzle('near-goal', 'The final stretch', 84, 92, 'Both players are close. Compare all 11 choices before deciding.'),
        Puzzle('free-points', 'Read the digits', 61, 87, 'Inspect the guaranteed Boar Brawl gain and compare it with rolling.'),
        Puzzle('level-table', 'A level table', 52, 52, 'A tied score does not make all moves equal. Find a model-best move.'),
        Puzzle('one-point', 'One point away', 99, 99, 'More than one move may be equally strong. Any model-best choice is accepted.'),
    )


def check_answer(puzzle, count):
    if type(count) is not int or not 0 <= count <= 10:
        raise ValueError('Choose 0-10 dice.')
    report = coach_position(puzzle.score, puzzle.opponent)
    return count in report.best_choices, report
