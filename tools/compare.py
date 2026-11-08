"""Compare matched-seed league reports, resampling whole matches."""

import argparse
import json
import random
import statistics
from pathlib import Path


def load_rows(paths):
    rows = {}
    for name in paths:
        report = json.loads(Path(name).read_text(encoding="utf-8"))
        for row in report["results"]:
            rows[row["opponent"]] = {run["seed"]: run for run in row["runs"]}
    return rows


def compare(old_paths, new_paths):
    old, new = load_rows(old_paths), load_rows(new_paths)
    rows = []
    groups = []
    for opponent in sorted(old.keys() & new.keys()):
        seeds = sorted(old[opponent].keys() & new[opponent].keys())
        if not seeds:
            continue
        pairs = [(old[opponent][s], new[opponent][s]) for s in seeds]
        if any(a["hands"] != b["hands"] for a, b in pairs):
            raise ValueError("matched runs must have equal hand counts")
        differences = [(b["match_points"] - a["match_points"],
                        b["bb_per_hand"] - a["bb_per_hand"]) for a, b in pairs]
        groups.append(differences)
        rows.append({"opponent": opponent, "matched_matches": len(seeds),
                     "match_point_delta": statistics.mean(d[0] for d in differences),
                     "bb_per_hand_delta": statistics.mean(d[1] for d in differences)})
    if not groups:
        raise ValueError("reports have no matched opponents and seeds")
    rng = random.Random(44677)
    bootstrap = []
    for _ in range(4000):
        bootstrap.append(statistics.mean(
            statistics.mean(rng.choice(group)[0] for _ in group) for group in groups))
    bootstrap.sort()
    return {"comparisons": rows,
            "equal_weight_match_point_delta": statistics.mean(r["match_point_delta"] for r in rows),
            "equal_weight_bb_per_hand_delta": statistics.mean(r["bb_per_hand_delta"] for r in rows),
            "paired_bootstrap_95pct_point_delta": [bootstrap[100], bootstrap[3899]],
            "note": "Development-only comparison. Opponent mixture is synthetic; interval is approximate."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", nargs="+", required=True)
    parser.add_argument("--new", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = compare(args.old, args.new)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
