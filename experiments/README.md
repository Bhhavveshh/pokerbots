# Reproducible improvement experiments

`snapshots/*.zip` are immutable runnable policies. `snapshot.json` inside each
archive records the exact file hashes; the report also hashes the whole archive.
Opponents based on our original policy always run from `v1.zip`, even after live
source changes. `opponents/independent_v1.zip` freezes two separately written
equity/polarized policies. These share the card evaluator, but none of our betting,
range, preflop-table or discard-policy implementation.

## Development panel

Every tracking candidate uses `improve-track-v1-0` through `-5` against the same
starter, aggressive, reference and frozen-v1 opponents. All are normal 400-hand
duplicate matches. This panel is used for selection and is not held-out data.

```powershell
python -m tools.experiments evaluate example --version v2 --flags '{"consistent_flop":true,"discard_signal":false,"preflop_table":true}'
python -m tools.improvement_report
```

Use a new label; completed reports and snapshots cannot be overwritten. The local
private Python 3.11 interpreter is documented in the root README. Reports ending
in `.partial.json` are checkpoints, not separate experiments. Low sample counts
and selection among several candidates limit confidence in tracking gains.

## Final panel

`final_plan.json` is written only after the production candidate is selected and
frozen as `v4.zip`. It predeclares 20 matches per opponent against reference,
frozen-v1 and both independent policies, using fresh `improve-final-v1-*` seeds.
Each opponent's baseline and candidate run sequentially on the same logical CPU.
There is no strategy tuning after opening these seeds. Combined `p4_baseline.json`
and `p4_candidate.json` contain the same runs as their four opponent shards; do
not add both combined and shard counts when calculating totals.

```powershell
python -m tools.final_evaluation lock
python -m tools.final_evaluation shard --opponent reference --cpu 0
python -m tools.final_evaluation shard --opponent frozen_v1 --cpu 2
python -m tools.final_evaluation shard --opponent equity --cpu 4
python -m tools.final_evaluation shard --opponent polar --cpu 6
python -m tools.final_evaluation collect
python -m tools.improvement_report
python -m tools.build_report
```

Shard commands are independent; each complete match and its child processes use
one CPU. Reports retain affinity, normal charged clocks, notices, stderr bytes,
memory samples, seeds and source hashes. External machine load and wall-clock
sample cutoffs can change decisions despite fixed RNG seeds. Fixed-work replay
tests disable the sample clock only to compare policy logic; no win-rate or
runtime measurement disables the official clocks.

Intervals resample whole seed blocks across opponents, not individual hands.
The synthetic panel does not represent the unknown tournament field. A gain,
loss or inconclusive result is reported as measured rather than forced into a
monotonically rising progress curve.

## Diagnostic experiments

- `discard_audit.json`: synthetic common-world showdown equity, not match wins.
- `preflop_training.json`: offline generation of 1,755 three-card suit classes;
  equity ordering mapped to a similar opening frequency, not equilibrium charts.
- `cfr_validation.json`: known Kuhn value and exact best-response tests on finite
  one-bet games. This is not measured exploitability of full Discard Hold'em.
- `decisions.json`: what was retained/rejected, evidence and uncertainty per phase.

The original v1 build evidence remains in `reports/discard_holdem/`. The earlier
ordinary two-card Hold'em experiment at `reports/` root is historical only.
