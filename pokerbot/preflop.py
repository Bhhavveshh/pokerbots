"""Read-only, suit-isomorphic preflop data generated offline for this variant."""

import json
from functools import lru_cache
from importlib.resources import files
from itertools import permutations


def canonical(hole):
    best = None
    for order in permutations(hole):
        suits = {}
        normalized = []
        for card in order:
            suit = suits.setdefault(card % 4, len(suits))
            normalized.append((card // 4) * 4 + suit)
        key = tuple(sorted(normalized))
        if best is None or key < best:
            best = key
    return ",".join(str(card) for card in best)


@lru_cache(maxsize=1)
def table():
    data = json.loads(files("pokerbot").joinpath("preflop_data.json").read_text(encoding="utf-8"))
    if data["variant"] != "Discard Hold'em" or data["version"] != 1:
        raise ValueError("unsupported preflop data")
    return data["hands"]


def strength(hole):
    return table()[canonical(hole)]["strength_score"]
