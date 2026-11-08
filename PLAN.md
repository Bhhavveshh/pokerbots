# Pokerbot development

## Working assumptions

The organizer has only specified Texas Hold'em and the runtime constraints. The
local game is heads-up, no-limit, no rake, blinds 1/2, 200 chips per player, and
stacks reset every hand. These are configurable development assumptions, not
confirmed tournament rules. The JSONL adapter is our own development protocol.
Official integration requires the actual protocol and legal-action semantics.

## Four sequential phases

1. **Correct foundation:** independent evaluator checks, betting engine,
   transparent baseline opponents, and duplicate-deal evaluation.
2. **Range-aware strategy:** positional preflop decisions, weighted opponent
   hands, bounded equity sampling, and response-aware postflop decisions.
3. **Adaptation and measurement:** shrinkage-based opponent statistics, bounded
   adjustments, time allocation, varied opponents, and strategy ablations.
4. **Submission hardening:** Python 3.11 checks, protocol failure tests, full-length
   held-out matches, reproducible reports, and a self-contained source archive.

Each phase runs correctness tests and produces measured results before the next.
Development seeds and final evaluation seeds stay separate. Results against our
local opponents cannot establish performance against unknown tournament teams.

## Completion status

- Phase 1 complete: betting/evaluator tests and baseline duplicate league.
- Phase 2 complete: range-aware policy tested against five local opponents.
- Phase 3 complete: adaptive candidate and matched-seed strategy ablation.
- Phase 4 local checks complete: Python 3.11 tests, exhaustive evaluator check,
  frozen 80-match held-out league, and two guarded 1,000-hand subprocess matches.

See `RESULTS.md` for observations, uncertainty, timing and integration limits.
Official tournament integration is pending the actual protocol, process lifecycle,
complete rules and the organizer's runtime. The archives are development bundles.

## Priorities

- P0: legal play, correct settlement, fast evaluator, baseline, runtime protection.
- P1: ranges, action selection, cautious adaptation, independent evaluation.
- P2: offline CFR or additional search only if P0/P1 are complete and experiments
  demonstrate an advantage. They are not part of the initial implementation.
