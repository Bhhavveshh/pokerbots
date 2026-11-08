"""Build current results from the locked final panel and runtime verification."""

import hashlib
import json
import zipfile
from pathlib import Path

from tools.experiments import ROOT, summary
from tools.official_match import RUNTIME_FILES, snapshot


def read(name):
    return json.loads((ROOT / "reports/improvements" / name).read_text(encoding="utf-8"))


def main():
    plan = json.loads((ROOT / "experiments/final_plan.json").read_text())
    release = json.loads((ROOT / "experiments/release.json").read_text())
    if snapshot() != release["source_sha256"]:
        raise AssertionError("Current runtime differs from selected release")
    archive = ROOT / "experiments/snapshots/v4.zip"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != plan["candidate_snapshot_sha256"]:
        raise AssertionError("Frozen candidate archive changed")
    with zipfile.ZipFile(archive) as z:
        files = json.loads(z.read("snapshot.json"))["files"]
        for name, expected in files.items():
            if hashlib.sha256(z.read(name)).hexdigest() != expected:
                raise AssertionError("Frozen candidate source corrupted: " + name)
    with zipfile.ZipFile(ROOT / release["snapshot"]) as z:
        if hashlib.sha256((ROOT / release["snapshot"]).read_bytes()).hexdigest() != release["snapshot_sha256"]:
            raise AssertionError("Selected release archive changed")
        for name in RUNTIME_FILES:
            if z.read(name) != (ROOT / name).read_bytes():
                raise AssertionError("Production source differs from tested release: " + name)
    base, final, comparison = [read(name) for name in
        ("p4_baseline.json", "p4_candidate.json", "final_comparison.json")]
    tests = json.loads((ROOT / "reports/release/tests.json").read_text())
    if not tests["passed"]:
        raise AssertionError("Correctness tests failed")
    runs = base["runs"] + final["runs"]
    if any(r["forfeits"] or r["candidate_notices"] or r["candidate_stderr_bytes"] or
           any(leg["notices"] or leg["stderr_bytes"] for leg in r["legs"]) or
           r["hands_played"] != r["hands_scheduled"] for r in runs):
        raise AssertionError("Final comparison contains invalid or incomplete matches")
    lines = ["# Discard Hold'em: four-phase results", "",
        "The default bot is the selected **v1 baseline**, byte-identical to its tested snapshot.",
        "The v4 candidate and its complete experimental evidence are preserved for later work.",
        "The full experiment ledger, retained/rejected changes and development uncertainty",
        "are in [IMPROVEMENT_LOG.md](IMPROVEMENT_LOG.md). `experiments/final_plan.json` was",
        "locked before opening the final seeds. No strategy was tuned on final results.", "",
        "## Development progress", "",
        "| Selected version | Wins / matches | Win rate | BB/hand |",
        "|---|---:|---:|---:|"]
    decisions = json.loads((ROOT / "experiments/decisions.json").read_text())
    selections = [("Original v1", "p0_baseline")] + [
        (f"Phase {d['phase']}", d["selected_label"]) for d in decisions if d["phase"] <= 3]
    for label, name in selections:
        s = summary(read(name + ".json")["runs"])
        lines.append(f"| {label} | {s['wins']}/{s['matches']} | {s['wins']/s['matches']:.1%} | {s['bb_per_hand']:+.4f} |")
    lines += ["", "These are repeated DEVELOPMENT comparisons on six shared seed blocks against",
        "starter/aggressive/reference/frozen-v1. Selection and wall-clock sampling variation",
        "mean this table is not evidence of a guaranteed or monotonic increase in strength.", "",
        "## Fresh-seed final comparison", "",
        "80 full Stage 1 matches per version: 20 against each of four frozen opponents.",
        "Every match uses both fresh-process legs, swapped duplicate deals, 400 scheduled",
        "hands, normal official clocks and one logical CPU. Baseline and candidate use the",
        "same seeds and the same CPU for each opponent. Independently authored equity/polar",
        "policies share our card evaluator but none of our range, action or discard code.", "",
        "| Opponent | Baseline v1 wins / 20 | Candidate v4 wins / 20 | Baseline BB/hand | Candidate BB/hand |",
        "|---|---:|---:|---:|---:|"]
    for opponent in plan["opponents"]:
        a,b = [summary([r for r in d["runs"] if r["opponent"] == opponent]) for d in (base,final)]
        lines.append(f"| {opponent} | {a['wins']} | {b['wins']} | {a['bb_per_hand']:+.4f} | {b['bb_per_hand']:+.4f} |")
    a,b = base["summary"],final["summary"]
    pair = comparison["paired"]
    ci = pair["point_delta_95pct_bootstrap"]
    chip_ci = pair["chip_delta_95pct_bootstrap"]
    lines += ["", f"Baseline v1: **{a['wins']}/{a['matches']} wins ({a['wins']/a['matches']:.1%})**, {a['draws']} draws.",
        f"Candidate v4: **{b['wins']}/{b['matches']} wins ({b['wins']/b['matches']:.1%})**, {b['draws']} draws.",
        f"Each version played {b['hands']:,} hands. The two versions together played {a['hands']+b['hands']:,} hands.", "",
        f"Paired match-point change: **{pair['point_delta']:+.3f}** per match; approximate 95%",
        f"whole-seed-block bootstrap interval **[{ci[0]:+.3f}, {ci[1]:+.3f}]** ({pair['seed_blocks']} blocks).",
        f"Chip change: {pair['bb_per_hand_delta']:+.4f} BB/hand; interval [{chip_ci[0]:+.4f}, {chip_ci[1]:+.4f}]."]
    if ci[0] <= 0 <= ci[1]:
        lines += ["", "The interval includes zero: this panel does **not** establish a reliable improvement."]
    elif ci[0] > 0:
        lines += ["", "This panel supports an improvement against these local opponents; it does not",
                  "establish an advantage over the unknown tournament field."]
    else:
        lines += ["", "This fresh panel indicates a regression. The result is retained rather than hidden",
                  "or used for post-hoc tuning; further development needs new evaluation seeds."]
    capped = sum(r["capped_delta"] for r in final["runs"]) / sum(r["hands_scheduled"] for r in final["runs"])
    lines += ["", f"Candidate v4 capped tiebreak score on this schedule: {capped:+.4f} chips per hand.",
        "BB/hand is raw chips / scheduled hands / 2. Match points, rather than chip totals",
        "against passive bots, are the primary selection objective. Paired blocks contain",
        "the same deal seed across all opponents; individual hands are not independent samples.", "",
        "## Release choice", "",
        "At the user's request, the working source and `dist/discard-holdem-submission.zip`",
        "now use the v1 baseline with the best observed result. `dist/discard-holdem-baseline.zip`",
        "is an alias of that release. `dist/discard-holdem-experimental-v4.zip` preserves the",
        "frozen v4 candidate; its editable agent is `pokerbot/experimental_agent.py`.",
        "The historical candidate and its test results were not altered. Promoting the existing",
        "baseline is a release acceptance decision, not a tuned replacement policy.",
        "The sample does not establish that either version is universally stronger.", "",
        "## Runtime and correctness", "",
        f"Python 3.11.9 correctness suite: **{tests['tests']} tests passed**.",
        "Runtime audit hooks reject bot file mutations, sockets and child processes.",
        "The unchanged supplied runner enforces real startup, per-reply, bank and wall limits.", "",
        "| Stage / opponent | Hands | Leg 1 charged | Leg 2 charged | Bank / leg | Peak memory |",
        "|---|---:|---:|---:|---:|---:|"]
    for name in ("runtime_stage1.json","runtime_stage2.json","runtime_reference.json"):
        r = json.loads((ROOT / "reports/release" / name).read_text())
        if not r["passed"] or r["source_sha256"] != release["source_sha256"]:
            raise AssertionError("Runtime evidence is stale or failed")
        legs = [x for x in r["legs"] if x["bot"] == "A"]
        peak = max(x["peak_working_set_bytes"] for x in legs) / 1024**2
        bank = 30 if r["stage"] == 1 else 75
        lines.append(f"| {r['stage']} / {r['opponent']} | {r['hands_played']} | "
                     f"{legs[0]['charged_seconds']:.3f}s | {legs[1]['charged_seconds']:.3f}s | {bank}s | {peak:.1f} MiB |")
    lines += ["", "Final comparisons and guarded runs had no forfeits, candidate notices or stderr errors.",
        "The submission ZIP is additionally imported directly and run through the official",
        "engine by `tools.package`; its size/hash are in `dist/manifest.json`.", "",
        "## Game theory and remaining limits", "",
        "The v4 candidate uses range-conditioned sampled equity, pot odds, expected action payoffs,",
        "a conservative common-sample discard choice and shrunk opponent adaptation. The",
        "offline preflop table is simulated equity ordering, not an equilibrium chart.",
        "The experimental CFR implementation uses genuine counterfactual regrets and average",
        "strategies; Kuhn value and exact finite-game best responses are tested. Its one-bet,",
        "four-bucket river game omits actual raises and many private-card distinctions.",
        "Toy exploitability does not measure full-game exploitability or give safe-subgame guarantees.", "",
        "Local Windows single-CPU tests cannot certify the organizer's Linux server sandbox.",
        "Tournament opponents, organizer updates and an actual server submission remain unverified.",
        "The old two-card results are obsolete; `reports/discard_holdem/` is historical v1 evidence.", ""]
    (ROOT / "RESULTS.md").write_text("\n".join(lines),encoding="utf-8")
    print("Built RESULTS.md from immutable final comparisons and matching runtime hashes")


if __name__ == "__main__":
    main()
