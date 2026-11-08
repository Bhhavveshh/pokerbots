"""Regenerate the experiment ledger from immutable reports and explicit decisions."""

import json
from pathlib import Path

from tools.experiments import ROOT, paired, summary


def main():
    directory = ROOT / "reports/improvements"
    reports = {path.stem: json.loads(path.read_text(encoding="utf-8"))
               for path in sorted(directory.glob("*.json")) if ".partial." not in path.name}
    reports = {name: r for name, r in reports.items() if "runs" in r and r.get("complete")}
    decisions_file = ROOT / "experiments/decisions.json"
    decisions = json.loads(decisions_file.read_text(encoding="utf-8")) if decisions_file.exists() else []
    lines = ["# Four-phase improvement ledger", "",
             "## Measurement contract", "",
             "Version v1 is the original Discard Hold'em candidate (commit d748434). Its old",
             "26/32 result is historical context, not the denominator for this improvement panel.",
             "Strategies and opponent implementations are frozen in ZIP snapshots. Every run",
             "uses the supplied official engine, full duplicate matches and normal clocks.", "",
             "The `improve-track-v1-*` panel is DEVELOPMENT data: the same opponents and seeds",
             "are used to compare versions. It is not described as held-out evaluation. Final",
             "validation uses fresh seeds and separately compares baseline and final candidate.", "",
             "Win rate = wins / matches. Draws count as half a match point. Paired intervals",
             "resample complete deal-seed blocks across opponents. Small panels are exploratory.",
             "An observed increase is not proof of a universal causal improvement. One-switch",
             "ablations identify the tested change; bundled changes require separate ablations.", "",
             "Native wall-clock sample cutoffs can cascade through subsequent random choices.",
             "Repeated equivalent controls therefore need not have identical outcomes. We keep",
             "same-code controls and do not attribute every cross-version delta to strategy.", "",
             "## Completed tracking experiments", "",
             "| Experiment | Version | W / D / L | Win rate | Match points | BB/hand |",
             "|---|---|---:|---:|---:|---:|"]
    for name, report in reports.items():
        if report["seed_prefix"] != "improve-track-v1":
            continue
        s = summary(report["runs"])
        lines.append(f"| {name} | {report['version']} | {s['wins']} / {s['draws']} / {s['losses']} | "
                     f"{100*s['wins']/s['matches']:.1f}% ({s['matches']} matches) | {s['match_points']:.3f} | {s['bb_per_hand']:+.4f} |")
    if "p0_baseline" in reports:
        base = reports["p0_baseline"]
        lines += ["", "## Paired changes from v1 on the tracking panel", "",
                  "| Experiment | Point change | Approx. 95% interval | BB/hand change |",
                  "|---|---:|---|---:|"]
        for name, report in reports.items():
            if name == "p0_baseline" or report["seed_prefix"] != base["seed_prefix"]:
                continue
            try:
                result = paired(base, report)
            except ValueError:
                continue
            ci = result["point_delta_95pct_bootstrap"]
            lines.append(f"| {name} | {result['point_delta']:+.3f} | [{ci[0]:+.3f}, {ci[1]:+.3f}] | "
                         f"{result['bb_per_hand_delta']:+.4f} |")
    lines += ["", "## Comparisons against same-code controls", "",
              "| Control | Candidate | Point change | Approx. 95% interval | BB/hand change |",
              "|---|---|---:|---|---:|"]
    for control, candidate in (("p2_control", "p2_exact"), ("p2_control", "p2_responses"),
                               ("p2_control", "p2_preflop"), ("p2_control", "p2_bundle"),
                               ("p3_control", "p3_cfr")):
        if control in reports and candidate in reports:
            r = paired(reports[control], reports[candidate])
            lo, hi = r["point_delta_95pct_bootstrap"]
            lines.append(f"| {control} | {candidate} | {r['point_delta']:+.3f} | "
                         f"[{lo:+.3f}, {hi:+.3f}] | {r['bb_per_hand_delta']:+.4f} |")
    lines += ["", "## Phase decisions and likely causes", ""]
    if not decisions:
        lines += ["Phase 1 measurements are running. No winning candidate has been selected yet.", ""]
    for decision in decisions:
        selection_label = "Frozen evaluated candidate" if decision["phase"] == 4 else "Selected experiment"
        lines += [f"### Phase {decision['phase']}: {decision['title']}", "",
                  f"{selection_label}: `{decision['selected_label']}`.", "", decision["reason"], "",
                  "Evidence: " + ", ".join(f"`{label}`" for label in decision["evidence"]) + ".", "",
                  "Limits: " + decision["limitations"], ""]
    lines += ["## Final fresh-seed validation", ""]
    final_reports = [reports[name] for name in ("p4_baseline", "p4_candidate") if name in reports]
    if not final_reports:
        lines.append("Pending completion of Phases 1–3. Tracking results are not final held-out results.")
    for report in final_reports:
        s = summary(report["runs"])
        lines.append(f"- `{report['label']}`: {s['wins']}/{s['matches']} wins, {s['draws']} draws, "
                     f"{s['bb_per_hand']:+.4f} BB/hand, {s['hands']:,} hands.")
    if len(final_reports) == 2:
        result = paired(final_reports[0], final_reports[1])
        ci = result["point_delta_95pct_bootstrap"]
        lines += ["", f"Paired match-point change: {result['point_delta']:+.3f}; approximate 95%",
                  f"whole-seed-block bootstrap interval [{ci[0]:+.3f}, {ci[1]:+.3f}].",
                  "Aggregate reports contain the same runs as the four opponent shards; do not double count."]
    release_file = ROOT / "experiments/release.json"
    if release_file.exists():
        release = json.loads(release_file.read_text())
        lines += ["", "## Current default release", "",
                  f"At the user's request, `{release['version']}` is now the default `bot.py` and submission ZIP.",
                  "Its runtime is byte-identical to the selected snapshot. The v4 experiment remains",
                  "preserved in its archive and editable experimental agent; historical results above",
                  "are unchanged. Release hashes are in `experiments/release.json`; fresh verification",
                  "is in `reports/release/`."]
    lines += ["", "All snapshots, flags, seeds, source hashes, per-opponent outcomes and timing",
              "remain in `experiments/` and `reports/improvements/`. Rejected candidates remain",
              "visible; the production bot is not automatically changed by this report.", ""]
    (ROOT / "IMPROVEMENT_LOG.md").write_text("\n".join(lines), encoding="utf-8")
    print("Updated IMPROVEMENT_LOG.md from", len(reports), "completed experiments")


if __name__ == "__main__":
    main()
