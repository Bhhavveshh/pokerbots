"""Predeclared final panel, immutable shards, paired aggregation; no tuning here."""

import argparse
import hashlib
import json

from tools.experiments import DIRECTORY, ROOT, evaluate, opponent_hash, paired, summary
from tools.official_match import snapshot
from tools.runtime_support import one_cpu

OPPONENTS = ("reference", "frozen_v1", "equity", "polar")
PLAN = DIRECTORY / "final_plan.json"


def lock():
    if PLAN.exists():
        raise ValueError("Final evaluation plan is immutable")
    archive = DIRECTORY / "snapshots/v4.zip"
    if not archive.exists():
        raise ValueError("Select and freeze the final candidate before opening final seeds")
    plan = {"baseline_version":"v1", "candidate_version":"v4", "candidate_flags":{},
            "candidate_snapshot_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
            "source_sha256":snapshot(), "opponents":OPPONENTS,
            "opponent_sha256":{name:opponent_hash(name) for name in OPPONENTS},
            "stage":1, "matches_per_opponent":20, "seed_prefix":"improve-final-v1",
            "selection":"Locked before fresh seeds. Keep candidate unchanged regardless of results.",
            "method":"Baseline then candidate on each opponent's same logical CPU; native clocks, full duplicate matches."}
    PLAN.write_text(json.dumps(plan,indent=2)+"\n",encoding="utf-8")
    print("Locked final evaluation plan")


def read_plan():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    archive = DIRECTORY / "snapshots" / (plan["candidate_version"] + ".zip")
    if hashlib.sha256(archive.read_bytes()).hexdigest() != plan["candidate_snapshot_sha256"]:
        raise AssertionError("Frozen final candidate changed")
    if {name:opponent_hash(name) for name in OPPONENTS} != plan["opponent_sha256"]:
        raise AssertionError("Frozen opponent changed")
    return plan


def shard(opponent, cpu):
    plan, affinity = read_plan(), one_cpu(cpu)
    for label, version, flags in (("baseline",plan["baseline_version"],{}),
                                  ("candidate",plan["candidate_version"],plan["candidate_flags"])):
        name = f"p4_{label}_{opponent}"
        path = ROOT / "reports/improvements" / (name + ".json")
        if path.exists():
            raise ValueError("Completed final shards must not be rerun")
        evaluate(name,version,flags,[opponent],plan["matches_per_opponent"],
                 plan["seed_prefix"],stage=plan["stage"],affinity=affinity)


def collect():
    plan = read_plan()
    reports = {}
    for label in ("baseline", "candidate"):
        shards = [json.loads((ROOT / "reports/improvements" / f"p4_{label}_{opponent}.json").read_text())
                  for opponent in OPPONENTS]
        if not all(d["complete"] and len(d["runs"]) == plan["matches_per_opponent"] for d in shards):
            raise AssertionError("Final panel incomplete")
        if any(leg["notices"] or leg["stderr_bytes"]
               for shard in shards for run in shard["runs"] for leg in run["legs"]):
            raise AssertionError("A final-panel opponent or candidate produced notices/stderr")
        report = dict(shards[0])
        report.update(label="p4_"+label,opponents=list(OPPONENTS),
                      runs=[r for shard in shards for r in shard["runs"]])
        report["summary"] = summary(report["runs"])
        report["shard_affinity"] = {opponent:d["affinity"] for opponent,d in zip(OPPONENTS,shards)}
        report["affinity"] = "see shard_affinity"
        report["opponent_sha256"] = plan["opponent_sha256"]
        reports[label] = report
        path = ROOT / "reports/improvements" / (report["label"] + ".json")
        if path.exists():
            raise ValueError("Combined final reports are immutable")
        path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    result = {"paired":paired(reports["baseline"],reports["candidate"]),
              "baseline":reports["baseline"]["summary"], "candidate":reports["candidate"]["summary"],
              "plan_sha256":hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(",",":")).encode()).hexdigest(),
              "plan_hash_format":"SHA256 of canonical JSON: sorted keys, compact separators, UTF-8",
              "no_tuning_on_final_seeds":True}
    (ROOT / "reports/improvements/final_comparison.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result,indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("lock","shard","collect"))
    parser.add_argument("--opponent",choices=OPPONENTS)
    parser.add_argument("--cpu",type=int,default=0)
    args=parser.parse_args()
    if args.action == "lock":
        lock()
    elif args.action == "collect":
        collect()
    elif args.opponent is None:
        parser.error("shard requires --opponent")
    else:
        shard(args.opponent,args.cpu)


if __name__ == "__main__":
    main()
