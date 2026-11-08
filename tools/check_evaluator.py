"""Exhaust all 2,598,960 five-card hands and independently cross-check 7-card hands."""

import json
import random
import time
from itertools import combinations
from pathlib import Path

from pokerbot.cards import CATEGORY_NAMES, evaluate, reference_evaluate


def main():
    start = time.perf_counter()
    counts = [0] * 9
    for hand in combinations(range(52), 5):
        counts[evaluate(hand) >> 20] += 1
    expected = [1302540, 1098240, 123552, 54912, 10200, 5108, 3744, 624, 40]
    if counts != expected:
        raise AssertionError((counts, expected))
    rng = random.Random(11777)
    for _ in range(20000):
        hand = rng.sample(range(52), 7)
        if evaluate(hand) != reference_evaluate(hand):
            raise AssertionError(hand)
    result = {"five_card_hands": sum(counts), "category_counts": dict(zip(CATEGORY_NAMES, counts)),
              "independent_seven_card_checks": 20000, "seed": 11777,
              "seconds": time.perf_counter() - start, "passed": True}
    Path("reports").mkdir(exist_ok=True)
    Path("reports/evaluator.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
