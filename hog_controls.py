"""Portable, conflict-free shortcuts. No arbitrary Tcl binding expressions."""

ACTIONS = ('Roll', 'Pause / resume', 'Restart', 'Coach', 'Theme', 'Mute',
           'Dashboard', 'Rules', 'Choose 10 dice')
DEFAULT_KEYS = ('Return', 'p', 'r', 'h', 't', 'm', 'Escape', 'F1', 'x')
KEY_CHOICES = ('Return', 'Escape') + tuple('abcdefghijklmnopqrstuvwxyz') + tuple(f'F{i}' for i in range(1, 13))


def validate_shortcuts(keys):
    if not isinstance(keys, (list, tuple)) or len(keys) != len(ACTIONS):
        raise ValueError('Choose one key for each action.')
    if any(type(key) is not str or key not in KEY_CHOICES for key in keys):
        raise ValueError('Use a letter, Return, Escape, or F1-F12. Digits stay reserved for dice.')
    if len(set(keys)) != len(keys):
        raise ValueError('Each action needs a different key.')
    return tuple(keys)


def shortcut_summary(keys):
    return '   /   '.join(f'{action}: {key}' for action, key in zip(ACTIONS, keys))
