"""Summarize recorded experiments without selecting or modifying a strategy."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / "reports" / name).read_text(encoding="utf-8"))


def totals(report):
    runs = [run for row in report["results"] for run in row["runs"]]
    return (len(runs), sum(run["hands"] for run in runs),
            sum(run["match_points"] == 1 for run in runs),
            sum(run["match_points"] == 0.5 for run in runs),
            sum(run["match_points"] == 0 for run in runs))


def main():
    heldout = read("phase4_heldout.json")
    for name, digest in heldout["source_sha256"].items():
        if hashlib.sha256((ROOT / "pokerbot" / name).read_bytes()).hexdigest() != digest:
            raise AssertionError("Core source changed after held-out freeze: " + name)
    tests, evaluator = read("tests.json"), read("evaluator.json")
    if not tests["passed"] or not evaluator["passed"]:
        raise AssertionError("Correctness verification failed")
    comparison = read("phase3_comparison.json")
    phases = [("1: foundation", read("phase1.json")),
              ("2: range-aware", read("phase2.json")),
              ("3: adaptive development", read("phase3_adaptive.json")),
              ("4: held-out", heldout)]
    lines = [
        "# Measured local results", "",
        "All four local development phases are complete. Official rule/protocol integration",
        "and verification on the organizer's runtime remain outstanding. No upload was made.", "",
        "## Experimental conditions", "",
        "Heads-up no-limit Hold'em, 1/2 blinds, 200-chip starting stacks reset every hand,",
        "no rake. Each shuffled deck is played twice with bots swapping seats. These",
        "settings are assumptions because complete tournament rules have not been supplied.", "",
        "Development seed family: 110800 + match_index * 1009. Held-out family: 880000 +",
        "match_index * 1009. The strategy was frozen before inspecting held-out results;",
        "the report verifies that the current core files still match the recorded hashes.", "",
        "## Phase progression", "",
        "| Phase | Candidate | Matches | Hands | Wins | Draws | Losses |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for name, report in phases:
        count, hands, wins, draws, losses = totals(report)
        lines.append(f"| {name} | {report['candidate']} | {count} | {hands:,} | {wins} | {draws} | {losses} |")
    lines += ["", "The opponent sets grow between phases; raw win rates are not a controlled",
              "comparison across all four rows. Phase 3 has a separate matched-seed comparison",
              "against 48 range-bot matches, using six common seeds per opponent.", "",
              f"Adaptive minus range bot: **{comparison['equal_weight_match_point_delta']:+.4f} match points per match**",
              f"and **{comparison['equal_weight_bb_per_hand_delta']:+.4f} BB/hand**, averaging opponent types equally.",
              f"Approximate paired bootstrap 95% interval for the match-point difference:",
              f"{comparison['paired_bootstrap_95pct_point_delta']}. It includes zero; the limited",
              "sample does not establish a statistically reliable match-point improvement.", "",
              "## Frozen held-out league", "",
              "| Opponent | W / D / L | BB/hand | Approx. 95% half-width | Match points / match |",
              "|---|---:|---:|---:|---:|"]
    for row in heldout["results"]:
        runs = row["runs"]
        w = sum(r["match_points"] == 1 for r in runs)
        d = sum(r["match_points"] == 0.5 for r in runs)
        l = len(runs) - w - d
        lines.append(f"| {row['opponent']} | {w} / {d} / {l} | {row['mean_bb_per_hand']:+.4f} | "
                     f"{row['approx_95pct_half_width']:.4f} | {row['match_point_rate']:.3f} |")
    count, hands, wins, draws, losses = totals(heldout)
    fallbacks = sum(row["budget_fallbacks"] for row in heldout["results"])
    lines += ["", f"Total: **{wins} wins, {draws} draws, {losses} losses across {count} matches and {hands:,} hands**.",
              f"The league completed without illegal actions or crashes. Recorded budget fallbacks: {fallbacks}.",
              "The process was pinned to one logical CPU. League timing excludes subprocess I/O.", "",
              "## Runtime integration checks", "",
              "Persistent Python 3.11 subprocess, JSONL decisions and terminal events, one logical",
              "CPU. Audit hooks reject filesystem writes, network socket operations and child",
              "process creation inside the bot. These hooks are diagnostics, not an OS sandbox.", "",
              "| Opponent | Hands | Transport-inclusive bank time | Peak working set | Errors |",
              "|---|---:|---:|---:|---:|"]
    for filename in ("runtime_calling.json", "runtime_equity.json"):
        row = read(filename)
        if not row["passed"]:
            raise AssertionError("Runtime validation failed")
        lines.append(f"| {row['opponent']} | {row['hands']} | {row['transport_inclusive_bank_seconds']:.3f} s | "
                     f"{row['process_peak_working_set_bytes'] / 1048576:.2f} MiB | {len(row['errors'])} |")
    lines += ["", "Bank measurements include startup wait, serialization, response wait and terminal",
              "messages; they exclude development-engine and opponent computation between requests.",
              "This is local Windows/Python 3.11.9 evidence. It does not reproduce the organizer's",
              "Linux CPU speed or certify its 1 GB/read-only/network sandbox.", "",
              "## Correctness checks", "",
              f"- Python 3.11 suite: {tests['tests']} tests, {tests['failures']} failures, {tests['errors']} errors.",
              f"- Exhaustive category counts: all {evaluator['five_card_hands']:,} five-card hands match expected frequencies.",
              f"- Independent oracle: {evaluator['independent_seven_card_checks']:,} additional seeded seven-card hands agree.",
              "- Tests cover kickers, wheel straights, paired boards, full houses, all-in settlement,",
              "  raise limits, duplicate cancellation, sampled-card exclusion, exhausted budgets,",
              "  malformed JSON, duplicate requests, terminal actions and direct/adapter parity.", "",
              "## Limits and next integration step", "",
              "These are locally authored synthetic opponents. Some share policy code with our bot.",
              "They are not a representative sample of tournament entrants. Neither positive chip",
              "rates nor local match wins prove low exploitability or future tournament success.",
              "The approximate intervals use whole matches and normal approximations; eight matches",
              "per opponent still provide limited evidence. The official chip cap is unknown and",
              "has not been substituted with an invented formula.", "",
              "Next: map the official protocol, verify actual stack/betting rules and process lifetime,",
              "and rerun legality/runtime tests in the provided environment. Until then the ZIPs",
              "are development bundles rather than verified tournament submissions.", ""]
    (ROOT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Held-out: {wins}/{count} wins; {hands:,} hands. Wrote RESULTS.md.")


if __name__ == "__main__":
    main()
