# Discard Hold'em: four-phase results

The runtime is frozen as `v4.zip`; its file hashes match the current bot.
The full experiment ledger, retained/rejected changes and development uncertainty
are in [IMPROVEMENT_LOG.md](IMPROVEMENT_LOG.md). `experiments/final_plan.json` was
locked before opening the final seeds. No strategy was tuned on final results.

## Development progress

| Selected version | Wins / matches | Win rate | BB/hand |
|---|---:|---:|---:|
| Original v1 | 18/24 | 75.0% | +5.4848 |
| Phase 1 | 20/24 | 83.3% | +5.8831 |
| Phase 2 | 20/24 | 83.3% | +5.9670 |
| Phase 3 | 20/24 | 83.3% | +6.0321 |

These are repeated DEVELOPMENT comparisons on six shared seed blocks against
starter/aggressive/reference/frozen-v1. Selection and wall-clock sampling variation
mean this table is not evidence of a guaranteed or monotonic increase in strength.

## Fresh-seed final comparison

80 full Stage 1 matches per version: 20 against each of four frozen opponents.
Every match uses both fresh-process legs, swapped duplicate deals, 400 scheduled
hands, normal official clocks and one logical CPU. Baseline and candidate use the
same seeds and the same CPU for each opponent. Independently authored equity/polar
policies share our card evaluator but none of our range, action or discard code.

| Opponent | Original wins / 20 | Final wins / 20 | Original BB/hand | Final BB/hand |
|---|---:|---:|---:|---:|
| reference | 13 | 12 | +0.1863 | +0.1061 |
| frozen_v1 | 10 | 8 | -0.1319 | -0.3805 |
| equity | 20 | 20 | +4.7561 | +4.7061 |
| polar | 20 | 20 | +4.3069 | +4.5581 |

Original: **63/80 wins (78.8%)**, 0 draws.
Final: **60/80 wins (75.0%)**, 0 draws.
Each version played 32,000 hands. The two versions together played 64,000 hands.

Paired match-point change: **-0.037** per match; approximate 95%
whole-seed-block bootstrap interval **[-0.138, +0.062]** (20 blocks).
Chip change: -0.0319 BB/hand; interval [-0.2487, +0.1655].

The interval includes zero: this panel does **not** establish a reliable improvement.

Final capped tiebreak score on this schedule: +0.4695 chips per hand.
BB/hand is raw chips / scheduled hands / 2. Match points, rather than chip totals
against passive bots, are the primary selection objective. Paired blocks contain
the same deal seed across all opponents; individual hands are not independent samples.

## Release choice

The working source and `dist/discard-holdem-submission.zip` preserve frozen v4 as
an experimental candidate. `dist/discard-holdem-baseline.zip` exports byte-exact
v1 runtime files as the conservative submission alternative. The candidate and
its test results were not altered after final evaluation. Exporting the existing
baseline is a release acceptance decision, not a tuned replacement policy.
The sample does not establish that either version is universally stronger.

## Runtime and correctness

Python 3.11.9 correctness suite: **69 tests passed**.
Runtime audit hooks reject bot file mutations, sockets and child processes.
The unchanged supplied runner enforces real startup, per-reply, bank and wall limits.

| Stage / opponent | Hands | Leg 1 charged | Leg 2 charged | Bank / leg | Peak memory |
|---|---:|---:|---:|---:|---:|
| 1 / starter | 400 | 3.216s | 2.952s | 30s | 17.1 MiB |
| 2 / starter | 1000 | 13.830s | 10.587s | 75s | 17.2 MiB |
| 2 / reference | 1000 | 5.076s | 4.926s | 75s | 17.1 MiB |

Final comparisons and guarded runs had no forfeits, candidate notices or stderr errors.
The submission ZIP is additionally imported directly and run through the official
engine by `tools.package`; its size/hash are in `dist/manifest.json`.

## Game theory and remaining limits

The v4 candidate uses range-conditioned sampled equity, pot odds, expected action payoffs,
a conservative common-sample discard choice and shrunk opponent adaptation. The
offline preflop table is simulated equity ordering, not an equilibrium chart.
The experimental CFR implementation uses genuine counterfactual regrets and average
strategies; Kuhn value and exact finite-game best responses are tested. Its one-bet,
four-bucket river game omits actual raises and many private-card distinctions.
Toy exploitability does not measure full-game exploitability or give safe-subgame guarantees.

Local Windows single-CPU tests cannot certify the organizer's Linux server sandbox.
Tournament opponents, organizer updates and an actual server submission remain unverified.
The old two-card results are obsolete; `reports/discard_holdem/` is historical v1 evidence.
