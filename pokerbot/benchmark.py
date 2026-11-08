"""Paired duplicate matches. All uncertainty is computed across whole matches."""

import argparse
import hashlib
import json
import math
import random
import statistics
import platform
import sys
import time
from dataclasses import asdict
from pathlib import Path

from .bots import BOT_TYPES, register_strategies
from .game import Engine, GameConfig

register_strategies()


def run_match(candidate, opponent, pairs, seed, config=None):
    config = config or GameConfig()
    rng = random.Random(seed)
    bots = (BOT_TYPES[candidate](seed=seed + 101), BOT_TYPES[opponent](seed=seed + 307))
    engine = Engine(config)
    profits = []
    decisions = [0, 0]
    elapsed = [0.0, 0.0]
    max_decision = [0.0, 0.0]

    class Timed:
        def __init__(self, bot, index):
            self.bot, self.index = bot, index

        def start_hand(self, seat, hand_id):
            start = time.perf_counter()
            self.bot.start_hand(seat, hand_id)
            elapsed[self.index] += time.perf_counter() - start

        def observe(self, event):
            start = time.perf_counter()
            self.bot.observe(event)
            elapsed[self.index] += time.perf_counter() - start

        def act(self, obs):
            start = time.perf_counter()
            action = self.bot.act(obs)
            duration = time.perf_counter() - start
            elapsed[self.index] += duration
            max_decision[self.index] = max(max_decision[self.index], duration)
            decisions[self.index] += 1
            return action

    wrapped = (Timed(bots[0], 0), Timed(bots[1], 1))
    start = time.perf_counter()
    for pair in range(pairs):
        deck = list(range(52))
        rng.shuffle(deck)
        first = engine.play(wrapped, deck, button=pair % 2, hand_id=pair * 2)
        second = engine.play(wrapped[::-1], deck, button=pair % 2, hand_id=pair * 2 + 1)
        profits.append(first.profits[0] + second.profits[1])
    total = sum(profits)
    return {
        "seed": seed, "hands": pairs * 2, "profit_chips": total,
        "bb_per_hand": total / (pairs * 2 * config.big_blind),
        "match_points": 1.0 if total > 0 else 0.5 if total == 0 else 0.0,
        "candidate_seconds": round(elapsed[0], 6),
        "candidate_decisions": decisions[0],
        "max_decision_seconds": round(max_decision[0], 6),
        "budget_fallbacks": getattr(bots[0], "fallbacks", 0),
        "wall_seconds": round(time.perf_counter() - start, 6),
    }


def league(candidate, opponents, pairs, matches, seed, config=None):
    config = config or GameConfig()
    rows = []
    for name in opponents:
        results = [run_match(candidate, name, pairs, seed + i * 1009, config)
                   for i in range(matches)]
        values = [r["bb_per_hand"] for r in results]
        # A rough normal interval is descriptive; few matches give weak evidence.
        half_width = (1.96 * statistics.stdev(values) / math.sqrt(matches)
                      if matches > 1 else None)
        row = {
            "opponent": name, "matches": matches, "hands": pairs * 2 * matches,
            "mean_bb_per_hand": statistics.mean(values),
            "approx_95pct_half_width": half_width,
            "match_point_rate": statistics.mean(r["match_points"] for r in results),
            "max_candidate_seconds": max(r["candidate_seconds"] for r in results),
            "max_decision_seconds": max(r["max_decision_seconds"] for r in results),
            "budget_fallbacks": sum(r["budget_fallbacks"] for r in results),
            "runs": results,
        }
        rows.append(row)
        print(f"{candidate:12s} vs {name:12s}: {row['mean_bb_per_hand']:+.4f} bb/hand; "
              f"points {row['match_point_rate']:.3f}; "
              f"max bot time {row['max_candidate_seconds']:.3f}s", flush=True)
    return {"candidate": candidate, "config": asdict(config), "pairs_per_match": pairs,
            "seed": seed, "matches_per_opponent": matches, "results": rows,
            "python": sys.version, "platform": platform.platform(),
            "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted(Path(__file__).parent.glob("*.py"))},
            "limitations": ["Local synthetic opponents; not tournament performance.",
                            "Timing excludes imports, process startup and protocol I/O.",
                            "Chip cap and organizer protocol are not yet specified.",
                            "Intervals are approximate and computed across matches."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bot", choices=BOT_TYPES, default="baseline")
    parser.add_argument("--opponents", nargs="+", choices=BOT_TYPES,
                        default=["calling", "tight", "aggressive", "random"])
    parser.add_argument("--pairs", type=int, default=200)
    parser.add_argument("--matches", type=int, default=5)
    parser.add_argument("--seed", type=int, default=110800)
    parser.add_argument("--stack", type=int, default=200)
    parser.add_argument("--output")
    parser.add_argument("--one-cpu", action="store_true")
    args = parser.parse_args()
    if args.pairs < 1 or args.matches < 1:
        parser.error("pairs and matches must be positive")
    affinity = None
    if args.one_cpu:
        from tools.runtime_support import one_cpu
        affinity = one_cpu()
    report = league(args.bot, args.opponents, args.pairs, args.matches,
                    args.seed, GameConfig(stack=args.stack))
    report["affinity"] = affinity
    if args.one_cpu:
        from tools.runtime_support import peak_memory_bytes
        report["process_peak_working_set_bytes"] = peak_memory_bytes()
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
