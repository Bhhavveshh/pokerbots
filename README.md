# Pokerbot

An original Python Hold'em bot, a development engine, and a duplicate-deal league.
Python **3.11**, standard library only. No runtime installation, network access,
trained model download, or third-party poker implementation is required.

## Rules we are assuming

The organizer has specified Texas Hold'em but has not supplied the complete rules
or protocol. Our local environment is **heads-up no-limit**, blinds **1/2**, stacks
**200 chips (100 BB)**, no ante or rake, and fresh stacks every hand. Stack and
blind sizes are configurable through `GameConfig`. They are development
assumptions, not verified tournament settings. We have not implemented unknown
custom mechanics or a match tie-break cap.

## Four phases

The milestones and priorities are in [PLAN.md](PLAN.md). Machine-readable results
are saved in `reports/`; development seeds begin at 110800. Final evaluation uses
a separate seed family and is kept out of parameter selection.

1. Correct evaluator, betting engine, baseline opponents, duplicate deals.
2. Weighted opponent ranges, sampled equity, positional preflop rules, bet EV.
3. Conservative opponent adaptation, time management, expanded opponent league.
4. Protocol hardening, Python 3.11 verification, held-out evaluation, packaging.

## Run tests and experiments

From this directory with Python 3.11:

```powershell
python -m unittest discover -v
python tools/run_tests.py
python -m pokerbot.benchmark --bot baseline --pairs 200 --matches 8 --seed 110800
python -m pokerbot.benchmark --bot adaptive --opponents baseline calling tight aggressive random equity switching shove --pairs 200 --matches 6 --seed 110800 --output reports/development.json
python tools/check_evaluator.py
python -B bot.py
```

On this Windows workspace a private Python 3.11.9 embedded interpreter is available
at `.tools/python311/python.exe`; it is excluded from the source archive. The
system Python is 3.13, so use the private interpreter for competition-version
checks. No packages were installed into the bot runtime.

`--pairs 200` means 400 hands. Each shuffled deck is played twice with the bots
swapping seats while cards and button remain fixed. The two results are combined.
Bot memory persists through a match, resets between matches, and never receives
the hidden opponent cards or the undealt runout. No duplicate-hand card lookup is
implemented.

## How decisions work

- **Preflop:** a transparent starting-hand score, position, raise history, price,
  and sampled equity when facing a raise. Opening and re-raising thresholds are
  heuristics, not solved poker charts.
- **Beliefs:** a bounded set of 160 possible opponent hands. Public actions update
  their weights. Known cards eliminate impossible hands. Hand-strength features
  are cached only for the current hand.
- **Equity:** up to 128 showdown samples per decision, with ties worth half a pot.
  Unknown opponent cards are excluded from each sampled board runout.
- **Actions:** compare calling/checking with selected half-pot and pot-sized
  raises, projected opponent continuation, and continuation-weighted showdown
  outcomes. Uncalled chips are excluded from the amount at risk.
- **Adaptation:** preflop/postflop fold statistics start with 20 prior observations;
  aggression has a separate prior. Adjustments are capped. Opponent range
  inference is softened for loose or aggressive play.
- **Time:** small per-decision deadlines plus a cumulative reserve. When the
  internal bank reaches its reserve, use a legal check/fold fallback.

The method does not solve future betting rounds, opponent re-raises, or equilibrium
strategies. It uses a heuristic equity-realization discount before the river.
Particle approximation and model errors can be exploited by strong opponents.

## Source map

| File | Responsibility |
|---|---|
| `pokerbot/cards.py` | Fast evaluator and independent slow testing oracle |
| `pokerbot/game.py` | Betting, legal actions, private observations, settlement |
| `pokerbot/bots.py` | Simple baseline opponents |
| `pokerbot/strategy.py` | Ranges, equity, action EV, adaptation, time management |
| `pokerbot/opponents.py` | Additional equity-based and changing-style opponents |
| `pokerbot/benchmark.py` | Seeded duplicate matches and league reports |
| `pokerbot/protocol.py` | Validated development JSONL adapter and terminal events |
| `tests/` | Correctness, edge cases and integration regressions |
| `tools/compare.py` | Matched-seed development comparison and bootstrap interval |
| `tools/check_evaluator.py` | Exhaustive category counts and independent oracle checks |
| `tools/validate_runtime.py` | Single-CPU subprocess matches with audit guards |

The message contract and examples are in [PROTOCOL.md](PROTOCOL.md). It includes
match reset, decisions and hand-end notifications. Until official details arrive,
this adapter is a development interface and must not be assumed upload-compatible.

```powershell
python -m pokerbot.benchmark --bot adaptive --opponents baseline calling tight aggressive random equity value switching shove range --pairs 200 --matches 8 --seed 880000 --one-cpu --output reports/phase4_heldout.json
python tools/validate_runtime.py --opponent calling --pairs 500 --seed 990100 --output reports/runtime_calling.json
python tools/validate_runtime.py --opponent equity --pairs 500 --seed 990101 --output reports/runtime_equity.json
python tools/package.py
```

The runtime ZIP contains the bot modules and protocol documentation; the source
ZIP also includes tests, development tools and reports. Packaging verifies a real
decision imported directly from the runtime archive under Python 3.11.

After the recorded final checks, `python tools/build_report.py` regenerates
[RESULTS.md](RESULTS.md) and verifies that the core strategy files still match the
held-out run's hashes. `reports/tests.json` is written by `tools/run_tests.py`.

## Interpreting results

Match-point rate is the average of win=1, draw=0.5 and loss=0. Chip rates are
reported in **big blinds per hand**, not BB/100. Approximate intervals are based on
whole independent matches, not individual paired hands. With few matches those
intervals are weak evidence. Opponent styles are synthetic and do not represent
the unknown tournament field. Multiple opponents share parts of our code.

Benchmark bot time includes callbacks and decisions but excludes interpreter
startup, protocol I/O, and time spent inside the development engine. Hardware
speed and timing cutoffs affect results. Passing local tests does not verify the
organizer's sandbox or establish tournament compatibility.
