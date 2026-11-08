# Discard Hold'em Pokerbot

Python 3.11 bot for the supplied Pokerbots **Discard Hold'em** competition.
Standard library only; no runtime installation, writes, sockets or subprocesses.
The competition entry point is `bot.py`.

## Actual rules

Three hole cards are dealt to each player. After flop betting, both players
simultaneously discard one card; both discards become public. Discarding still
happens after an all-in. Showdown uses the best five cards from the remaining two
hole cards and five board cards. Heads-up, 200 chips reset every hand, blinds 1/2,
and a four-bet/raise cap per street (the big blind counts preflop).

Each match has two legs with fresh processes and swapped seats/cards. Each process
sees every deal only once and keeps no state between legs. We do not attempt to
identify duplicate deals or transfer information across processes.

| Limit | Stage 1 | Stage 2 |
|---|---:|---:|
| Hands per leg | 200 | 500 |
| Time bank per leg | 30 s | 75 s |
| Wall limit per leg | 90 s | 225 s |
| Reply limit | 5 s | 5 s |
| Match chip cap | 400 | 1000 |

Limits marked provisional in the documents can be updated by the organizer. The
protocol also provides the current bank/hand count in `init` and bank remaining
on every request. The official startup grace is enforced by the supplied runner.

## Read the sources

The unmodified kit is in [official/Starter_Kit](official/Starter_Kit/README.md).
[official/README.md](official/README.md) records file hashes, document precedence,
and the audit of all three PDFs and supplied Python files. The documents prevail
if the local kit differs; no contradiction was found in the implemented paths.

**The initial ordinary two-card Hold'em experiment is superseded. Its 78/80 result
does not measure this game.** Historical modules/reports are retained for provenance
and regression checks, but are excluded from the submitted bot archive. Current
results are [RESULTS.md](RESULTS.md) and `reports/discard_holdem/` only.

## Test with the official engine

From this repository root using Python 3.11:

```powershell
python official/Starter_Kit/engine.py bot.py official/Starter_Kit/bot.py --seed example
python official/Starter_Kit/engine.py bot.py official/Starter_Kit/example_bots/random_bot.py --stage 2 --seed example-finals
python -m tools.run_tests
```

This workspace has a private Python 3.11.9 interpreter at
`.tools/python311/python.exe`; the default system Python is 3.13. Substitute that
interpreter when reproducing competition-version checks. It is excluded from Git
and the submission. No packages are required.

```powershell
python -m tools.official_match --opponents starter tight aggressive reference --matches 3 --stage 1 --seed-prefix discard-dev --label development --one-cpu --output reports/discard_holdem/development.json
python -m tools.official_match --opponents starter tight aggressive shove switching reference no_signal fast_discard --matches 4 --stage 1 --seed-prefix discard-heldout-v1 --label heldout --one-cpu --output reports/discard_holdem/heldout.json
python -m tools.validate_runtime --opponent starter --stage 1 --seed discard-guard-stage1 --output reports/discard_holdem/runtime_stage1.json
python -m tools.validate_runtime --opponent starter --stage 2 --seed discard-guard-stage2 --output reports/discard_holdem/runtime_stage2.json
python -m tools.validate_runtime --opponent reference --stage 2 --seed discard-guard-reference --output reports/discard_holdem/runtime_reference.json
python -m tools.build_report
python -m tools.package
```

All performance runs keep the official clocks enabled. Logs go to ignored `tmp/`
directories; aggregate evidence is saved under `reports/discard_holdem/`. The
metrics wrapper imports the supplied runner, records its results and clocks, and
does not alter dealing, betting, discards, scoring or timing semantics. Whole
matches, not individual paired hands, are the unit of uncertainty.

## How the bot works

1. Preflop, estimate three-card flexibility and use position, price, raise history
   and bounded Monte Carlo equity when facing a raise.
2. Before the discard, model opponent **triples**. A simulated hand chooses which
   two cards to keep using only that simulation's flop. It never chooses a pair
   using the simulated turn/river.
3. At the real discard, evaluate all three candidate pairs on shared random
   opponent hands/runouts. Prefer the draw-aware fast choice unless the paired
   samples give enough evidence to switch. Opponent choices are modeled from the
   flop only; simultaneous choices cannot observe one another.
4. Once discards are revealed, rebuild a range of opponent **pairs conditioned on
   the public discard**. Apply soft evidence about why that card was discarded,
   and replay observed public betting. Both discarded cards stay excluded from
   all future boards and remaining opponent cards.
5. Compare check/call/fold with a small set of legal raise sizes using sampled
   outcomes and an opponent continuation model. Fold/aggression estimates have
   priors and capped influence. Complete `hand_result` histories supply final
   actions missing from earlier decision requests.
6. Use the engine's `time_left_ms` with a reserve, bounded particles/samples and
   deadline checks. Low-bank decisions fall back to legal check/fold and a cheap
   flop-based discard.

This is an original heuristic policy, not a solved equilibrium or a guarantee of
tournament wins. It approximates future betting and discard behavior. Synthetic
opponents, especially those sharing our policy components, do not establish low
exploitability against other teams.

## Source map

| File | Current role |
|---|---|
| `bot.py` | Top-level submission entry point; disables bytecode writes |
| `pokerbot/protocol.py` | Official protocol 1.0 lifecycle, validation and replies |
| `pokerbot/agent.py` | Triple/pair beliefs, equity, action EV, adaptation and time |
| `pokerbot/discard.py` | Flop-only keep policy, draws and soft discard evidence |
| `pokerbot/cards.py` | Fast standard hand evaluator and testing oracle |
| `pokerbot/testing.py` | Locally authored seeded opponents; not submitted |
| `tools/official_match.py` | Metrics over the unmodified supplied match engine |
| `tools/validate_runtime.py` | Official full matches under runtime audit guards |
| `tests/test_official.py` | Variant, protocol, no-clairvoyance and engine regressions |

`pokerbot/game.py`, `strategy.py`, `bots.py`, `opponents.py`, `benchmark.py` and
`legacy_protocol.py` are the historical two-card experiment. Their old tests can
still run, but they are not imported by the current bot or included in its archive.

## Submission artifact

`python -m tools.package` creates `dist/discard-holdem-submission.zip`, with
`bot.py` at the top level and only the current runtime modules. It also refreshes
the previous runtime ZIP filename and creates a full source/reproducibility ZIP.
The packager enforces the 5 MB limit and verifies real protocol replies from the
archive without falling back to workspace modules. Run the packaged artifact
through the supplied engine before uploading. No Unstop upload is automated.
