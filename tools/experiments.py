"""Immutable strategy snapshots and paired official-runner improvement experiments."""

import argparse
import hashlib
import json
import random
import statistics
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools.official_match import RUNTIME_FILES, run_match
from tools.runtime_support import one_cpu

DIRECTORY = ROOT / "experiments"


def capture(name):
    path = DIRECTORY / "snapshots" / (name + ".zip")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError("Snapshots are immutable; choose a new version name")
    files = list(RUNTIME_FILES) + ["pokerbot/testing.py"]
    for extra in (ROOT / "pokerbot").glob("*.json"):
        files.append(extra.relative_to(ROOT).as_posix())
    hashes = {}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for filename in dict.fromkeys(files):
            data = (ROOT / filename).read_bytes()
            archive.writestr(filename, data)
            hashes[filename] = hashlib.sha256(data).hexdigest()
        archive.writestr("snapshot.json", json.dumps({"name": name, "files": hashes}, indent=2))
    print(f"Captured {name}: {path.stat().st_size} bytes", flush=True)
    return path


def entry(version, flags=None, opponent=None, timeless=False):
    path = DIRECTORY / "snapshots" / (version + ".zip")
    if not path.exists():
        raise ValueError("Unknown snapshot " + version)
    flags = flags or {}
    identity = hashlib.sha256((str(path) + json.dumps(flags, sort_keys=True) + str(opponent) + str(timeless)).encode()).hexdigest()[:16]
    target = ROOT / "tmp/experiment_entries" / identity / "bot.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    bootstrap = ("import sys, json\nsys.dont_write_bytecode = True\n"
                 f"sys.path.insert(0, {str(path)!r})\nimport pokerbot\n"
                 f"assert pokerbot.__file__.startswith({str(path)!r})\n")
    if timeless:
        # Logic regression tests only. Performance experiments never set this.
        bootstrap += "import pokerbot.agent\npokerbot.agent.time.perf_counter = lambda: 0.0\n"
    if opponent is not None and opponent != "full":
        code = bootstrap + f"from pokerbot.testing import run_opponent\nrun_opponent({opponent!r})\n"
    else:
        code = bootstrap + ("from pokerbot.protocol import ProtocolSession\nfrom pokerbot.agent import Config\n"
                            f"session = ProtocolSession(seed={7919 if opponent == 'full' else 20261108}, config=Config(**{flags!r}))\n"
                            "for line in sys.stdin:\n"
                            "    reply = session.handle(json.loads(line))\n"
                            "    if reply is not None:\n"
                            "        print(json.dumps(reply, separators=(',', ':')), flush=True)\n"
                            "    if session.finished:\n"
                            "        break\n")
    target.write_text(code, encoding="utf-8")
    return target


def opponent_entry(name):
    if name in ("equity", "polar"):
        archive = DIRECTORY / "opponents/independent_v1.zip"
        if not archive.exists():
            raise ValueError("Freeze the independent opponents first")
        target = ROOT / "tmp/independent_opponents" / name / "bot.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("import sys\nsys.dont_write_bytecode=True\n"
                          f"sys.path.insert(0, {str(archive)!r})\nimport pokerbot\n"
                          f"assert pokerbot.__file__.startswith({str(archive)!r})\n"
                          f"from pokerbot.benchmarks import main\nmain({name!r})\n", encoding="utf-8")
        return target
    if name == "starter":
        return ROOT / "official/Starter_Kit/bot.py"
    if name == "frozen_v1":
        return entry("v1", opponent="full")
    if name not in ("reference", "aggressive", "tight", "shove", "switching", "calling", "no_signal", "fast_discard"):
        raise ValueError("Unknown opponent " + name)
    return entry("v1", opponent=name)


def opponent_hash(name):
    path = (ROOT / "official/Starter_Kit/bot.py" if name == "starter" else
            DIRECTORY / "opponents/independent_v1.zip" if name in ("equity", "polar") else
            DIRECTORY / "snapshots/v1.zip")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summary(runs):
    return {"matches": len(runs), "wins": sum(r["match_points"] == 1 for r in runs),
            "draws": sum(r["match_points"] == 0.5 for r in runs),
            "losses": sum(r["match_points"] == 0 for r in runs),
            "match_points": statistics.mean(r["match_points"] for r in runs),
            "bb_per_hand": statistics.mean(r["bb_per_hand"] for r in runs),
            "hands": sum(r["hands_scheduled"] for r in runs)}


def evaluate(label, version, flags, opponents, matches, seeds, stage=1, affinity=None):
    path = ROOT / "reports/improvements" / (label + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise ValueError("Completed experiment reports are immutable")
    candidate = entry(version, flags)
    report = {"label": label, "version": version, "flags": flags, "seed_prefix": seeds,
              "stage": stage, "clocks_enabled": True, "affinity": affinity,
              "snapshot_sha256": hashlib.sha256((DIRECTORY / "snapshots" / (version + ".zip")).read_bytes()).hexdigest(),
              "opponents": opponents, "runs": [], "complete": False}
    report["opponent_sha256"] = {name: opponent_hash(name) for name in opponents}
    partial = path.with_suffix(".partial.json")
    for opponent in opponents:
        for i in range(matches):
            run = run_match(candidate, opponent_entry(opponent), stage, f"{seeds}-{i}",
                            log_dir=ROOT / "tmp/improvement_runs" / label / opponent / str(i))
            run["opponent"] = opponent
            report["runs"].append(run)
            partial.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            if run["forfeits"] or run["candidate_notices"] or run["candidate_stderr_bytes"]:
                raise RuntimeError("Experiment failed legality/runtime checks: " + run["log_dir"])
        row = summary([r for r in report["runs"] if r["opponent"] == opponent])
        print(f"{label} vs {opponent}: {row['wins']}/{row['matches']} wins, {row['bb_per_hand']:+.4f} BB/hand", flush=True)
    report["complete"] = True
    report["summary"] = summary(report["runs"])
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    # Keep the last checkpoint as an explicit completed checkpoint as well.
    partial.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def paired(old, new):
    a = {(r["opponent"], r["seed"]): r for r in old["runs"]}
    b = {(r["opponent"], r["seed"]): r for r in new["runs"]}
    if set(a) != set(b):
        raise ValueError("A paired comparison requires identical opponent/seed panels")
    blocks = {}
    for key in sorted(a):
        if a[key]["hands_scheduled"] != b[key]["hands_scheduled"]:
            raise ValueError("Match lengths differ")
        blocks.setdefault(key[1], []).append((b[key]["match_points"] - a[key]["match_points"],
                                             b[key]["bb_per_hand"] - a[key]["bb_per_hand"]))
    values = [(statistics.mean(x[0] for x in block), statistics.mean(x[1] for x in block))
              for block in blocks.values()]
    rng = random.Random(81173)
    bootstrap = [[], []]
    for _ in range(4000):
        sample = rng.choices(values, k=len(values))
        for index in (0, 1):
            bootstrap[index].append(statistics.mean(x[index] for x in sample))
    for distribution in bootstrap:
        distribution.sort()
    return {"point_delta": statistics.mean(x[0] for x in values),
            "bb_per_hand_delta": statistics.mean(x[1] for x in values),
            "point_delta_95pct_bootstrap": [bootstrap[0][100], bootstrap[0][3899]],
            "chip_delta_95pct_bootstrap": [bootstrap[1][100], bootstrap[1][3899]],
            "seed_blocks": len(values), "matched_matches": len(a),
            "note": "Whole seed blocks are resampled across all opponents; small panels are exploratory."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("capture", "evaluate"))
    parser.add_argument("name")
    parser.add_argument("--version", default="v1")
    parser.add_argument("--flags", default="{}")
    parser.add_argument("--opponents", nargs="+", default=["starter", "aggressive", "reference", "frozen_v1"])
    parser.add_argument("--matches", type=int, default=6)
    parser.add_argument("--seeds", default="improve-track-v1")
    parser.add_argument("--stage", type=int, choices=(1, 2), default=1)
    parser.add_argument("--cpu", type=int, default=0)
    args = parser.parse_args()
    if args.action == "capture":
        capture(args.name)
    else:
        affinity = one_cpu(args.cpu)
        evaluate(args.name, args.version, json.loads(args.flags), args.opponents,
                 args.matches, args.seeds, args.stage, affinity)


if __name__ == "__main__":
    main()
