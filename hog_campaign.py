"""Campaign catalog, objective evaluation and earned cosmetic definitions."""

from dataclasses import dataclass
from hog_showcase import replay_states


@dataclass(frozen=True)
class Stage:
    identifier: str
    title: str
    opponent: str
    strategy: str
    personality: str
    seed: int
    objectives: tuple


def stages():
    return (
        Stage('first-steps', 'First Steps', 'Milo', 'always5',
              'The steady host: always chooses five dice.', 3401, ('finish', 'win', 'zero1')),
        Stage('free-points', 'Free Points Bay', 'Nora', 'boar',
              'The opportunist: takes Boar Brawl when it earns at least 11 base points.', 3402, ('win', 'zero2', 'bonus1')),
        Stage('the-pursuit', 'The Pursuit', 'Dash', 'catch-up',
              'The chaser: chooses six dice when behind, otherwise five.', 3403, ('win', 'gain20', 'sow2')),
        Stage('prime-garden', 'Prime Garden', 'Iris', 'sus',
              'The prime seeker: includes Sus Fuss when considering the zero-dice option.', 3404, ('win', 'bonus2', 'zero1')),
        Stage('the-calculator', 'The Calculator', 'Quinn', 'medium',
              'The planner: maximizes exact expected immediate gain.', 3405, ('win', 'turns10', 'margin15')),
        Stage('summit', 'The Summit', 'Atlas', 'hard',
              'The strategist: maximizes model winning probability against optimal continuation.', 3406, ('win', 'sow2', 'gain25')),
    )


OBJECTIVES = {
    'finish': 'Complete the match (a loss still clears this stage)',
    'win': 'Win the match',
    'zero1': 'Choose zero dice at least once',
    'zero2': 'Choose zero dice at least twice',
    'bonus1': 'Receive at least one Sus Fuss bonus',
    'bonus2': 'Receive at least two Sus Fuss bonuses',
    'gain20': 'Gain at least 20 points in one turn, including bonus',
    'gain25': 'Gain at least 25 points in one turn, including bonus',
    'sow2': 'Finish with at most two Sow Sad turns',
    'turns10': 'Finish within ten of your own turns',
    'margin15': 'Win by at least 15 points',
}


def stage_by_id(identifier):
    for stage in stages():
        if stage.identifier == identifier:
            return stage
    raise ValueError('Unknown campaign stage.')


def objective_status(stage, session, events):
    turns = [event for event in events if event.player == 0]
    won = session.finished and session.winner == 0
    zero = sum(event.num_rolls == 0 for event in turns)
    bonus = sum(event.bonus > 0 for event in turns)
    largest = max((event.score_after - event.score_before for event in turns), default=0)
    sow = sum(1 in event.outcomes for event in turns)
    checks = {'finish': session.finished, 'win': won, 'zero1': zero >= 1, 'zero2': zero >= 2,
              'bonus1': bonus >= 1, 'bonus2': bonus >= 2, 'gain20': largest >= 20,
              'gain25': largest >= 25, 'sow2': session.finished and sow <= 2,
              'turns10': session.finished and len(turns) <= 10,
              'margin15': won and session.scores[0] - session.scores[1] >= 15}
    return tuple((OBJECTIVES[key], bool(checks[key])) for key in stage.objectives)


def evaluate_stage(stage, record):
    """The first objective clears a stage; optional stars require that clear.

    Best stars are a single-attempt result, not objectives combined over runs.
    """
    states = replay_states(record)
    class FinalTable:
        finished = True
        scores = states[-1]['scores']
        winner = 0 if scores[0] > scores[1] else 1
    events = [state['event'] for state in states[1:]]
    checks = objective_status(stage, FinalTable(), events)
    cleared = checks[0][1]
    return {'cleared': cleared, 'stars': sum(passed for _, passed in checks) if cleared else 0,
            'objectives': checks}


def available_stages(progress):
    unlocked = []
    for index, stage in enumerate(stages()):
        if index == 0 or progress.get(stages()[index - 1].identifier, {}).get('cleared', False):
            unlocked.append(stage.identifier)
    return tuple(unlocked)


@dataclass(frozen=True)
class Cosmetic:
    kind: str
    identifier: str
    title: str
    stars: int


def cosmetics():
    return (
        Cosmetic('dice', 'classic', 'Classic ivory', 0),
        Cosmetic('dice', 'cobalt', 'Cobalt blue', 3),
        Cosmetic('dice', 'ruby', 'Ruby red', 6),
        Cosmetic('dice', 'nebula', 'Nebula violet', 15),
        Cosmetic('avatar', 'initials', 'Your initials', 0),
        Cosmetic('avatar', 'panda', 'Panda', 5),
        Cosmetic('avatar', 'crown', 'Crown', 12),
        Cosmetic('theme', 'dark', 'Classic dark', 0),
        Cosmetic('theme', 'light', 'Classic light', 0),
        Cosmetic('theme', 'contrast', 'High contrast', 0),
        Cosmetic('theme', 'aurora', 'Aurora teal', 2),
        Cosmetic('theme', 'twilight', 'Twilight violet', 9),
    )


def earned_cosmetics(progress):
    stars = sum(row.get('stars', 0) for row in progress.values())
    return tuple(item for item in cosmetics() if item.stars <= stars)


def campaign_achievements(progress):
    cleared = sum(bool(row.get('cleared')) for row in progress.values())
    stars = sum(row.get('stars', 0) for row in progress.values())
    return (('First landing', min(cleared, 1), 1), ('Rising contender', min(cleared, 3), 3),
            ('Campaign champion', cleared, 6), ('Star collector', min(stars, 9), 9),
            ('Perfect trail', stars, 18))
