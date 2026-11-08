# Four-phase improvement ledger

## Measurement contract

Version v1 is the original Discard Hold'em candidate (commit d748434). Its old
26/32 result is historical context, not the denominator for this improvement panel.
Strategies and opponent implementations are frozen in ZIP snapshots. Every run
uses the supplied official engine, full duplicate matches and normal clocks.

The `improve-track-v1-*` panel is DEVELOPMENT data: the same opponents and seeds
are used to compare versions. It is not described as held-out evaluation. Final
validation uses fresh seeds and separately compares baseline and final candidate.

Win rate = wins / matches. Draws count as half a match point. Paired intervals
resample complete deal-seed blocks across opponents. Small panels are exploratory.
An observed increase is not proof of a universal causal improvement. One-switch
ablations identify the tested change; bundled changes require separate ablations.

Native wall-clock sample cutoffs can cascade through subsequent random choices.
Repeated equivalent controls therefore need not have identical outcomes. We keep
same-code controls and do not attribute every cross-version delta to strategy.

## Completed tracking experiments

| Experiment | Version | W / D / L | Win rate | Match points | BB/hand |
|---|---|---:|---:|---:|---:|
| p0_baseline | v1 | 18 / 0 / 6 | 75.0% (24 matches) | 0.750 | +5.4848 |
| p1_consistent_flop | v1a | 19 / 0 / 5 | 79.2% (24 matches) | 0.792 | +5.6470 |
| p1_consistent_no_signal | v1a | 20 / 0 / 4 | 83.3% (24 matches) | 0.833 | +5.8831 |
| p1_fast_discard | v1 | 20 / 0 / 4 | 83.3% (24 matches) | 0.833 | +5.4757 |
| p1_fast_no_signal | v1 | 16 / 0 / 8 | 66.7% (24 matches) | 0.667 | +5.5588 |
| p1_no_adapt | v1 | 18 / 0 / 6 | 75.0% (24 matches) | 0.750 | +4.4269 |
| p1_no_signal | v1 | 18 / 0 / 6 | 75.0% (24 matches) | 0.750 | +5.6761 |
| p2_bundle | v2 | 19 / 0 / 5 | 79.2% (24 matches) | 0.792 | +5.6523 |
| p2_control | v2 | 17 / 0 / 7 | 70.8% (24 matches) | 0.708 | +5.7393 |
| p2_exact | v2 | 17 / 0 / 7 | 70.8% (24 matches) | 0.708 | +5.5922 |
| p2_preflop | v2 | 20 / 0 / 4 | 83.3% (24 matches) | 0.833 | +5.9670 |
| p2_responses | v2 | 18 / 0 / 6 | 75.0% (24 matches) | 0.750 | +5.6767 |
| p3_cfr | v3 | 15 / 0 / 9 | 62.5% (24 matches) | 0.625 | +3.1315 |
| p3_control | v3 | 20 / 0 / 4 | 83.3% (24 matches) | 0.833 | +6.0321 |

## Paired changes from v1 on the tracking panel

| Experiment | Point change | Approx. 95% interval | BB/hand change |
|---|---:|---|---:|
| p1_consistent_flop | +0.042 | [-0.083, +0.167] | +0.1621 |
| p1_consistent_no_signal | +0.083 | [+0.000, +0.167] | +0.3983 |
| p1_fast_discard | +0.083 | [-0.083, +0.208] | -0.0091 |
| p1_fast_no_signal | -0.083 | [-0.208, +0.083] | +0.0740 |
| p1_no_adapt | +0.000 | [-0.125, +0.125] | -1.0579 |
| p1_no_signal | +0.000 | [+0.000, +0.000] | +0.1912 |
| p2_bundle | +0.042 | [-0.125, +0.208] | +0.1675 |
| p2_control | -0.042 | [-0.208, +0.125] | +0.2544 |
| p2_exact | -0.042 | [-0.167, +0.083] | +0.1073 |
| p2_preflop | +0.083 | [+0.000, +0.167] | +0.4822 |
| p2_responses | +0.000 | [-0.125, +0.125] | +0.1919 |
| p3_cfr | -0.125 | [-0.208, -0.042] | -2.3533 |
| p3_control | +0.083 | [-0.083, +0.208] | +0.5473 |

## Comparisons against same-code controls

| Control | Candidate | Point change | Approx. 95% interval | BB/hand change |
|---|---|---:|---|---:|
| p2_control | p2_exact | +0.000 | [-0.167, +0.167] | -0.1471 |
| p2_control | p2_responses | +0.042 | [-0.167, +0.250] | -0.0626 |
| p2_control | p2_preflop | +0.125 | [-0.083, +0.333] | +0.2278 |
| p2_control | p2_bundle | +0.083 | [-0.083, +0.292] | -0.0869 |
| p3_control | p3_cfr | -0.208 | [-0.375, +0.000] | -2.9006 |

## Phase decisions and likely causes

### Phase 1: Consistent flop policy and conservative discard inference

Selected experiment: `p1_consistent_no_signal`.

Development win rate rose from 18/24 (75.0%) to 20/24 (83.3%). At the tied 20-win score, this candidate earned more chips than disabling discard optimization. A shared selected pair is used in flop EV and the eventual discard. Uncalibrated policy inference from the opponent discard is disabled; dead-card blocking remains. Adaptation is retained: disabling it did not improve match points and reduced chip earnings. The two-feature interaction matters: disabling both optimization and inference fell to 16/24 and was rejected. An independent synthetic discard audit found only small showdown-equity gains, so the match improvement should not be described as simply choosing much better cards. The factored discard selector also fixes an original loop bug: when multiple alternatives clear the uncertainty threshold, it retains the highest mean rather than the last qualifying pair.

Evidence: `p0_baseline`, `p1_consistent_flop`, `p1_consistent_no_signal`, `p1_fast_discard`, `p1_fast_no_signal`, `p1_no_adapt`, `p1_no_signal`, `discard_audit`.

Limits: Six shared seed blocks; development selection among multiple candidates. Paired match-point bootstrap interval is [0, +0.167], and is exploratory. The estimated mechanism and improvement require fresh-seed confirmation. Matches on different logical cores may also differ slightly through sample deadlines. This selector correction is bundled into v1a, so the Phase 1 gain cannot be assigned exclusively to the consistency or inference flags. Fixed-work replay verifies its recorded fixture, not universal equivalence to the legacy selector.

### Phase 2: Calibrated preflop ordering; reject costly additions

Selected experiment: `p2_preflop`.

The preflop-only candidate won 20/24 (83.3%) with +5.9670 BB/hand, versus Phase 1 20/24 and +5.8831. On the same-code v2 control it gained three wins and +0.2278 BB/hand. Offline simulation ranks all 1,755 suit-equivalent triples under the actual flop-discard mechanics; its equity ordering replaces the hand-written ordering while roughly preserving opening frequency. Exact river enumeration won 17/24, the response model 18/24, and all three together 19/24, so those switches remain disabled.

Evidence: `p1_consistent_no_signal`, `p2_control`, `p2_preflop`, `p2_exact`, `p2_responses`, `p2_bundle`, `preflop_training`.

Limits: Six seed blocks give wide intervals: the preflop gain over same-code control has a point-change interval of [-0.0833,+0.3333]. The v2 control scored 17/24 versus the earlier equivalent v1a 20/24: fixed-work logic replay matches, but native wall-clock sampling cutoffs and tiny arithmetic changes can cascade through random sampling. Thus the cross-version difference is not attributed solely to preflop strategy. This is a development selection, not confirmed generalization.

### Phase 3: Validate CFR, reject its full-match deployment

Selected experiment: `p3_control`.

Actual vanilla CFR passed a 10,000-iteration Kuhn check: value -0.055546 versus known -1/18, exploitability 0.002318 versus uniform 0.458333. Six other finite games also converged under exact best-response evaluation. However the river-CFR candidate won only 15/24 (62.5%) versus its same-code control 20/24 (83.3%), losing 4 reference matches and 1 frozen-v1 match relative to control. Its chip change was -2.9006 BB/hand. Therefore CFR stays disabled; the Phase 2 policy is retained. Production defaults are changed to that selected configuration before freezing v4.

Evidence: `p2_preflop`, `p3_control`, `p3_cfr`, `cfr_validation`.

Limits: The solver is correct only for the restricted one-bet, four-bucket game. It uses sampled public ranges, heuristic reach inference, limited online iterations and omits real re-raises; those approximations plausibly explain poor transfer, but their individual causal contributions were not isolated. Toy exploitability is not full-game exploitability. The repeated control again won 20/24; its slightly higher chips are timing variation, not a new strategic improvement.

### Phase 4: Fresh evaluation does not confirm the development win-rate gain

Frozen evaluated candidate: `p4_candidate`.

The frozen v4 candidate won 60/80 (75.0%) versus v1 baseline 63/80 (78.75%) across 32,000 hands each. Paired point change -0.0375 has a 95% seed-block bootstrap interval [-0.1375,+0.0625]. Both versions won 20/20 against each independent equity/polar policy; candidate vs baseline was 12 vs 13 against reference, and 8 vs 10 against frozen-v1. Thus the tracking gain does not generalize convincingly to this fresh panel. No parameters or candidate code were changed after opening final seeds. The candidate is preserved as an experimental release; a byte-exact frozen v1 baseline artifact is provided as the conservative submission alternative. The candidate had lower charged time on this panel; timing details and full Stage 1/2 guarded checks are recorded separately.

Evidence: `p4_baseline`, `p4_candidate`, `final_comparison`, `final_timing`, `release_parity`, `tests`, `runtime_stage1`, `runtime_stage2`, `runtime_reference`.

Limits: The interval includes both benefit and harm; this is not proof of a regression or superiority. Synthetic opponents are not the tournament field, and two use related policy code. The baseline alternative is a release acceptance decision, not a tuned new policy; the final candidate and evaluation plan remain unchanged. Local Windows audit checks do not certify the organizer server.

## Final fresh-seed validation

- `p4_baseline`: 63/80 wins, 0 draws, +2.2793 BB/hand, 32,000 hands.
- `p4_candidate`: 60/80 wins, 0 draws, +2.2474 BB/hand, 32,000 hands.

Paired match-point change: -0.037; approximate 95%
whole-seed-block bootstrap interval [-0.138, +0.062].
Aggregate reports contain the same runs as the four opponent shards; do not double count.

## Current default release

At the user's request, `v1` is now the default `bot.py` and submission ZIP.
Its runtime is byte-identical to the selected snapshot. The v4 experiment remains
preserved in its archive and editable experimental agent; historical results above
are unchanged. Release hashes are in `experiments/release.json`; fresh verification
is in `reports/release/`.

All snapshots, flags, seeds, source hashes, per-opponent outcomes and timing
remain in `experiments/` and `reports/improvements/`. Rejected candidates remain
visible; the production bot is not automatically changed by this report.
