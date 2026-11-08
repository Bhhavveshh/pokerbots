"""Offline paired discard-quality diagnostic; not a tournament win-rate test."""

import json
import math
import random
import statistics
import time
from itertools import combinations
from pathlib import Path

from pokerbot.agent import Config, DiscardBot
from pokerbot.cards import evaluate
from pokerbot.discard import keep_fast
from tools.experiments import ROOT
from tools.runtime_support import one_cpu


def main():
    one_cpu(7)
    rng = random.Random(150913)
    rows = []
    started = time.perf_counter()
    for state in range(160):
        known = rng.sample(range(52), 6)
        original, flop = tuple(known[:3]), tuple(known[3:])
        pairs = tuple(combinations(original, 2))
        choices = [keep_fast(original, flop)]
        for consistent in (False, True):
            bot = DiscardBot(seed=9000 + state, config=Config(consistent_flop=consistent))
            bot.new_hand(1, original, True)
            bot.allowance = lambda time_left_ms, discard=False: 100.0
            # This diagnostic fixes the sample count. Official performance runs
            # always retain real clocks; there is no engine in this offline audit.
            if consistent:
                bot.sample_equity(flop, (), time.perf_counter() + 100)
                kept = bot.planned_keep
            else:
                discarded = bot.choose_discard(flop, 30000)
                kept = tuple(c for c in original if c != discarded)
            choices.append(kept)
        totals = [0.0, 0.0, 0.0]
        pool = [c for c in range(52) if c not in known]
        for _ in range(1024):
            sample = rng.sample(pool, 5)
            opponent = keep_fast(tuple(sample[:3]), flop)
            board = flop + tuple(sample[3:])
            theirs = evaluate(opponent + board)
            for i, pair in enumerate(pairs):
                ours = evaluate(pair + board)
                totals[i] += 1 if ours > theirs else 0.5 if ours == theirs else 0
        equities = [value / 1024 for value in totals]
        selected = [pairs.index(tuple(choice)) for choice in choices]
        rows.append({"state": state, "fast": equities[selected[0]],
                     "optimized": equities[selected[1]], "consistent": equities[selected[2]],
                     "optimized_switch": selected[1] != selected[0],
                     "consistent_switch": selected[2] != selected[0]})
    def delta(name):
        values = [r[name] - r["fast"] for r in rows]
        return {"mean_equity_delta_from_fast": statistics.mean(values),
                "approx_95pct_half_width": 1.96 * statistics.stdev(values) / math.sqrt(len(values))}
    report = {"states": len(rows), "independent_evaluation_worlds_per_state": 1024,
              "selection_samples": {"optimized": 128, "consistent": 96},
              "seed": 150913, "seconds": time.perf_counter() - started,
              "mean_equity": {name: statistics.mean(r[name] for r in rows)
                              for name in ("fast", "optimized", "consistent")},
              "optimized": delta("optimized"), "consistent": delta("consistent"),
              "rows": rows,
              "limitations": "Synthetic uniform opponent triples using a flop-only greedy discard. "
                              "This measures showdown equity, not betting EV or tournament win rate. "
                              "Fresh common evaluation worlds are not supplied to either selection policy."}
    path = ROOT / "reports/improvements/discard_audit.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2))


if __name__ == "__main__":
    main()
