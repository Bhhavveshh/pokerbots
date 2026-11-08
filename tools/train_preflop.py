"""Offline variant-specific preflop equity data; never executed inside the bot."""

import json
import math
import random
import time
from itertools import combinations
from pathlib import Path

from pokerbot.cards import evaluate
from pokerbot.discard import keep_fast, three_card_strength
from pokerbot.preflop import canonical
from tools.experiments import ROOT
from tools.runtime_support import one_cpu


def main():
    one_cpu(4)
    started = time.perf_counter()
    groups = {}
    old_scores = []
    for hand in combinations(range(52), 3):
        key = canonical(hand)
        if key not in groups:
            groups[key] = {"representative": tuple(map(int, key.split(","))), "multiplicity": 0}
        groups[key]["multiplicity"] += 1
        old_scores.append(three_card_strength(hand))
    rng = random.Random(611092)
    samples = 512
    for i, (key, row) in enumerate(sorted(groups.items())):
        hole = row["representative"]
        pool = [card for card in range(52) if card not in hole]
        total = total_squared = 0
        for _ in range(samples):
            dealt = rng.sample(pool, 8)
            opponent, board = tuple(dealt[:3]), tuple(dealt[3:])
            ours = evaluate(keep_fast(hole, board[:3]) + board)
            theirs = evaluate(keep_fast(opponent, board[:3]) + board)
            result = 1 if ours > theirs else 0.5 if ours == theirs else 0
            total += result
            total_squared += result * result
        row.update(equity=total / samples,
                   standard_error=math.sqrt(max(0, total_squared / samples - (total / samples) ** 2) / samples))
        if (i + 1) % 400 == 0:
            print(f"Preflop classes {i+1}/{len(groups)}", flush=True)
    # Preserve approximate opening/raising frequencies while improving the hand
    # ordering. This table is equity data, not a solved equilibrium strategy.
    old_scores.sort()
    offset = 0
    for key, row in sorted(groups.items(), key=lambda item: (item[1]["equity"], item[0])):
        midpoint = min(len(old_scores) - 1, offset + row["multiplicity"] // 2)
        row["strength_score"] = old_scores[midpoint]
        offset += row["multiplicity"]
    data = {"version": 1, "variant": "Discard Hold'em", "seed": 611092,
            "raw_starting_hands": 22100, "canonical_classes": len(groups), "samples_per_class": samples,
            "method": "Uniform opponent triples; both players select a pair using only the sampled flop. "
                      "Score is an equity-order quantile mapping to the old score distribution, not a GTO chart.",
            "hands": {key: {"equity": round(row["equity"], 7),
                             "standard_error": round(row["standard_error"], 7),
                             "strength_score": round(row["strength_score"], 7),
                             "multiplicity": row["multiplicity"]} for key, row in sorted(groups.items())}}
    destination = ROOT / "pokerbot/preflop_data.json"
    destination.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8", newline="\n")
    result = {"canonical_classes": len(groups), "raw_hands": offset,
              "samples_per_class": samples, "seed": 611092, "seconds": time.perf_counter() - started,
              "training_worlds": samples * len(groups), "runtime_data_bytes": destination.stat().st_size,
              "limitations": data["method"]}
    (ROOT / "reports/improvements/preflop_training.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
