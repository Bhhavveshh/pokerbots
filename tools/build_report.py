"""Summarize the official Discard Hold'em evidence; never tune strategy here."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.official_match import snapshot


def read(name):
    return json.loads((ROOT / "reports/discard_holdem" / name).read_text(encoding="utf-8"))


def totals(report):
    rows = report["results"]
    return {"wins": sum(r["wins"] for r in rows), "draws": sum(r["draws"] for r in rows),
            "losses": sum(r["losses"] for r in rows),
            "matches": sum(len(r["runs"]) for r in rows),
            "hands": sum(run["hands_played"] for r in rows for run in r["runs"])}


def main():
    development, heldout, tests = read("development.json"), read("heldout.json"), read("tests.json")
    if heldout["source_sha256"] != snapshot():
        raise AssertionError("Current runtime differs from frozen held-out code")
    if not tests["passed"]:
        raise AssertionError("Correctness suite failed")
    final = totals(heldout)
    lines = [
        "# Discard Hold'em: current measured results", "",
        "The bot was rebuilt from the three supplied PDFs and unchanged starter kit. The",
        "original two-card Hold'em policy/protocol is no longer the competition entry point.",
        "Its earlier **78/80** result is obsolete for this variant and is not reused here.", "",
        "## What changed", "",
        "- Official protocol 1.0, including silent notifications and process exit on `match_end`.",
        "- Three-card preflop/flop decisions, simultaneous discard requests even while all-in,",
        "  and post-discard pair ranges with both discards removed from future cards.",
        "- Common-sample discard comparison and soft inference from the public opponent discard.",
        "- Four-raise cap/short-all-in bounds taken from the engine's legal actions.",
        "- Two separate legs and per-leg timing; no cross-leg memory or duplicate identification.",
        "- Exact official capped-match score, replacing the old unknown-cap assumption.", "",
        "## Validation method", "",
        "All performance runs use the unmodified supplied `engine.py`, Python 3.11.9, its",
        "normal time banks, startup grace, per-reply deadlines and wall limits. A metrics",
        "wrapper records outcomes/charged clocks; it does not change game or timing logic.",
        "All seven kit files were checked byte-for-byte against the supplied ZIP.", "",
        "Each Stage 1 match is two fresh-process legs of 200 hands, with duplicate cards",
        "and seats swapped by the supplied runner. Development uses `discard-dev-*` seeds.",
        "The frozen evaluation uses fresh `discard-heldout-v1-*` seeds, four complete",
        "400-hand matches per opponent. No runtime code changed during or after that run.",
        "The report verifies the current runtime/engine hashes against the frozen snapshot.", "",
        "The process and children were pinned to one logical CPU for these runs. Local",
        "opponents are synthetic and some share our strategy code; this is not a sample",
        "of tournament entrants. Intervals below are approximate normal intervals over",
        "whole matches and are particularly uncertain with just four matches per opponent.", "",
        "## Phase results", "",
        "| Run | Matches | Hands | Wins | Draws | Losses |",
        "|---|---:|---:|---:|---:|---:|"]
    for label, report in (("Development", development), ("Frozen held-out", heldout)):
        t = totals(report)
        lines.append(f"| {label} | {t['matches']} | {t['hands']:,} | {t['wins']} | {t['draws']} | {t['losses']} |")
    lines += ["", "## Frozen opponent results", "",
              "| Opponent | W / D / L | BB/hand | Approx. 95% half-width | Match points / match |",
              "|---|---:|---:|---:|---:|"]
    all_runs = []
    for row in heldout["results"]:
        all_runs.extend(row["runs"])
        lines.append(f"| {row['opponent']} | {row['wins']} / {row['draws']} / {row['losses']} | "
                     f"{row['mean_bb_per_hand']:+.4f} | {row['approx_95pct_half_width']:.4f} | "
                     f"{row['match_point_rate']:.3f} |")
    if any(r["forfeits"] or r["candidate_notices"] or r["candidate_stderr_bytes"] for r in all_runs):
        raise AssertionError("Reported evaluation contains integration failures")
    capped = sum(r["capped_delta"] for r in all_runs) / sum(r["hands_scheduled"] for r in all_runs)
    lines += ["", f"Overall: **{final['wins']} wins, {final['draws']} draws, {final['losses']} losses**,",
              f"{final['matches']} matches and {final['hands']:,} hands; zero candidate corrections,",
              "forfeits or stderr errors. BB/hand is chips divided by hands and by the 2-chip big blind.",
              f"The exact capped score over this synthetic test schedule is {capped:+.4f} chips/hand.", "",
              "`starter` is the organizer's check/call + lowest-rank-discard bot. `tight`,",
              "`aggressive`, `shove`, and `switching` are our seeded heuristic stress opponents.",
              "`reference` uses our range/equity policy with adaptation, discard optimization",
              "and discard inference disabled. `no_signal` disables only discard inference;",
              "`fast_discard` disables only sampled discard optimization. They still block all",
              "known dead cards. Those comparisons are direct head-to-head ablations, not",
              "independent implementations or proof of any feature's value.", "",
              "**Weakness:** results against the range-aware reference and no-signal policy are",
              "not convincing. The sample is small, and it does not establish an advantage over",
              "these stronger related policies. The large profits against passive opponents",
              "must not be generalized to the tournament field. No equilibrium or exploitability",
              "guarantee is claimed. No parameters were tuned against these held-out seeds.", "",
              "## Full-length guarded runtime checks", "",
              "Audit hooks reject writes, socket operations and child-process creation inside",
              "the bot. The authoritative runner's clocks remain enabled. Audit hooks and",
              "affinity are local diagnostics, not a substitute for the organizer sandbox.", "",
              "| Stage / opponent | Hands | Leg 1 charged | Leg 2 charged | Bank per leg | Peak working set |",
              "|---|---:|---:|---:|---:|---:|"]
    for filename in ("runtime_stage1.json", "runtime_stage2.json", "runtime_reference.json"):
        row = read(filename)
        if not row["passed"] or row["source_sha256"] != snapshot():
            raise AssertionError("Missing/current runtime verification failed")
        legs = [leg for leg in row["legs"] if leg["bot"] == "A"]
        bank = 30 if row["stage"] == 1 else 75
        peak = max(leg["peak_working_set_bytes"] for leg in legs) / 1048576
        lines.append(f"| {row['stage']} / {row['opponent']} | {row['hands_played']} | "
                     f"{legs[0]['charged_seconds']:.3f} s | {legs[1]['charged_seconds']:.3f} s | {bank} s | {peak:.2f} MiB |")
    lines += ["", "Charged time is exactly the runner's measure: sending a request through receipt",
              "of its reply after applying the official startup grace. Each discard is charged",
              "too. Engine/opponent work between requests is not part of the bot's bank.",
              "Every recorded guarded match completed all scheduled hands with zero candidate",
              "notices, forfeits or stderr. The server's CPU speed/OS and upload portal remain",
              "unverified; the local machine runs Windows, not the organizer's Linux sandbox.", "",
              "## Correctness", "",
              f"- Python 3.11 suite: **{tests['tests']} tests**, zero failures/errors.",
              "- Current variant tests cover all-in discard, public blockers, conditioned pair",
              "  ranges, raise-cap bounds, protocol silence/exit, terminal history, fresh-leg reset,",
              "  and guards against choosing a discard using a simulated turn or river.",
              "- 1,200 additional seven-card hands agree with the organizer's independent evaluator.",
              "- Historical evaluator checks covered every five-card category frequency and",
              "  20,000 further seven-card oracle comparisons; the evaluator itself was retained.",
              "- Other retained tests concern the historical two-card implementation and are not",
              "  counted as evidence for Discard Hold'em strategic strength.", "",
              "## Artifacts and remaining work", "",
              "Run `python -m tools.package` to create `dist/discard-holdem-submission.zip`",
              "(bot.py at root, standard library only, below 5 MB), verify imports from the ZIP",
              "and play a packaged-bot match through the supplied runner. Its manifest records",
              "hashes and the package test. A separate source ZIP includes organizer materials,",
              "tests, tools and both historical/current reports with their scopes documented.", "",
              "No Unstop submission was made. Before the deadline, check organizer amendments",
              "to provisional values, verify the actual server sandbox if offered, and improve",
              "evaluation against independently designed stronger opponents. The bot is a tested",
              "competition-compatible local implementation, not an established winning strategy.", ""]
    (ROOT / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote RESULTS.md: {final['wins']}/{final['matches']} held-out wins, {final['hands']:,} hands")


if __name__ == "__main__":
    main()
