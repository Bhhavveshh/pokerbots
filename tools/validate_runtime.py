"""Timed official-runner match with runtime filesystem/network/process audit guards."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.official_match import opponent_path, run_match, snapshot
from tools.runtime_support import one_cpu


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--opponent", default="starter")
    parser.add_argument("--stage", type=int, choices=(1, 2), default=2)
    parser.add_argument("--seed", default="discard-runtime-1")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    affinity, source = one_cpu(), snapshot()
    report = run_match(ROOT / "tools/guarded_bot.py", opponent_path(args.opponent),
                       args.stage, args.seed, log_dir=ROOT / "tmp/official_guarded" / args.seed)
    if report["forfeits"] or report["candidate_notices"] or report["candidate_stderr_bytes"]:
        raise AssertionError("Guarded official match failed; inspect " + report["log_dir"])
    peaks = [leg["peak_working_set_bytes"] for leg in report["legs"] if leg["bot"] == "A"]
    if not all(0 < peak < 1024 ** 3 for peak in peaks):
        raise AssertionError("Missing or excessive candidate memory measurement")
    if snapshot() != source:
        raise AssertionError("Core source changed during runtime validation")
    report.update(opponent=args.opponent, source_sha256=source, affinity=affinity,
                  passed=True, audit_guards_enabled=True, clocks_enabled=True,
                  limitations="Unmodified supplied runner, with metrics instrumentation and audit guards. "
                              "Local Windows Python 3.11; does not certify the organizer Linux sandbox.")
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"hands": report["hands_played"], "stage": args.stage,
                      "candidate_legs": [leg for leg in report["legs"] if leg["bot"] == "A"],
                      "passed": True}, indent=2))


if __name__ == "__main__":
    main()
