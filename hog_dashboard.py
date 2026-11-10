"""Small presentation helpers shared by the dashboard and match table.

Everything here is derived from recorded data. Rendering never rolls dice.
"""

import json


def initials(name):
    """Use the first and last words, with a readable guest fallback."""
    words = name.split()
    if not words:
        return "?"
    return (words[0][0] + (words[-1][0] if len(words) > 1 else "")).upper()


def turn_breakdown(event):
    """Separate a turn's ordinary points from its Sus Fuss adjustment."""
    if event is None:
        return ("TURN POINTS", "—", "SUS FUSS", "—", "NEW SCORE", "—")
    source = "BOAR BRAWL" if event.num_rolls == 0 else "SOW SAD" if 1 in event.outcomes else "DICE TOTAL"
    return (source, f"+{event.turn_points}", "SUS FUSS", f"+{event.bonus}",
            "NEW SCORE", str(event.score_after))


def recent_results(history, limit=2):
    """Build compact summaries; skip unreadable records without modifying them."""
    results = []
    for row in history:
        try:
            payload = json.loads(row["payload"])
            names, scores = payload["config"]["names"], payload["scores"]
            if len(names) != 2 or len(scores) != 2:
                continue
            results.append((f"{names[0]} vs {names[1]}", f"{scores[0]} : {scores[1]}"))
        except (KeyError, ValueError, TypeError):
            continue
        if len(results) >= limit:
            break
    return results
