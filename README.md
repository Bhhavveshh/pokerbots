# Discard Hold'em Pokerbot

Python 3.11 bot for the supplied Pokerbots **Discard Hold'em** competition.
Standard library only; no runtime installation, writes, sockets or subprocesses.
The competition entry point is `bot.py`.

The four improvement phases are tracked in [IMPROVEMENT_LOG.md](IMPROVEMENT_LOG.md).
Immutable strategy snapshots and matched-seed comparisons live in `experiments/`
and `reports/improvements/`. Tracking data and final fresh-seed evaluation are
reported separately, including unsuccessful changes.

**Fresh validation did not confirm an improvement:** v1 won 63/80 matches; the
v4 candidate won 60/80. The working source is the frozen, faster v4 candidate.
Packaging also exports `dist/discard-holdem-baseline.zip` from the byte-exact v1
snapshot as the conservative submission alternative. Both artifacts contain
`bot.py` at ZIP root; see [RESULTS.md](RESULTS.md) before choosing an upload.

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
results are [RESULTS.md](RESULTS.md) and `reports/improvements/`. The original
Discard Hold'em v1 evidence remains in `reports/discard_holdem/`.

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
python -m tools.experiments evaluate reproduce-final --version v4 --opponents reference frozen_v1 equity polar --matches 20 --seeds improve-final-v1 --cpu 0
python -m tools.validate_cfr
python -m tools.improvement_report
python -m tools.build_report
python -m tools.package
```

The first command reproduces the frozen final comparison under a new report label.
Each match uses one CPU; it may take several minutes. Existing completed labels
cannot be overwritten. The original final plan, shard commands and hash records
are documented in [experiments/README.md](experiments/README.md).

All performance runs keep the official clocks enabled. Logs go to ignored `tmp/`
directories; aggregate evidence is saved under `reports/improvements/`. The
metrics wrapper imports the supplied runner and does not alter dealing, betting,
discards, scoring or timing semantics. Whole deal-seed blocks across opponents,
not individual hands, are the unit of paired uncertainty. Timed sample cutoffs
can introduce variation even with fixed RNG seeds.

## How the bot works

1. Preflop, use an offline simulated ordering of all 1,755 suit-equivalent
   three-card hands. Use position, price, raise history and bounded Monte Carlo
   equity when facing a raise. This is an equity table, not equilibrium charts.
2. Before the discard, model opponent **triples**. A simulated hand chooses which
   two cards to keep using only that simulation's flop. It never chooses a pair
   using the simulated turn/river.
3. Compare all three pairs on common sampled worlds and commit to one retained
   pair for flop equity and the actual discard. Prefer the fast draw-aware pair
   unless the paired samples justify switching. With no prior flop decision,
   evaluate at discard time. All-in discards still occur. Simultaneous choices
   cannot observe one another.
4. Once discards are revealed, rebuild the range of opponent **pairs** and replay
   observed public betting. Both discarded cards are excluded from future boards
   and remaining opponent cards. The uncalibrated heuristic about why the opponent
   chose that discard is disabled in the selected policy.
5. Compare check/call/fold with a small set of legal raise sizes using sampled
   outcomes and an opponent continuation model. Fold/aggression estimates have
   priors and capped influence. Complete `hand_result` histories supply final
   actions missing from earlier decision requests.
6. Use the engine's `time_left_ms` with a reserve, bounded particles/samples and
   deadline checks. Low-bank decisions fall back to legal check/fold and a cheap
   flop-based discard.

Exact river enumeration, a response-tree model and a genuine restricted river
CFR solver remain available behind configuration flags, disabled in the v4 candidate.
Their full-match evidence and rejected configurations are retained in the ledger.
The CFR solver passes known Kuhn-value and finite-game best-response checks. It
models only one bet size and four strength buckets, omitting actual re-raises.
This does not establish a full-game equilibrium or safe subgame guarantee.
The method follows the [original CFR research](https://proceedings.neurips.cc/paper/2007/hash/08d98638c6fcd194a4b1e6992063e944-Abstract.html); the implementation here is locally authored.

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
| `pokerbot/preflop.py`, `preflop_data.json` | Offline equity ordering loaded read-only |
| `pokerbot/cfr.py`, `river.py` | Experimental finite river-game CFR |
| `pokerbot/responses.py` | Optional weighted response-tree EV |
| `pokerbot/testing.py`, `benchmarks.py` | Locally authored test opponents; not submitted |
| `tools/experiments.py` | Immutable policies and paired tracking experiments |
| `tools/final_evaluation.py` | Locked fresh-seed baseline/final comparison |
| `tools/official_match.py` | Metrics over the unmodified supplied match engine |
| `tools/validate_runtime.py` | Official full matches under runtime audit guards |
| `tests/test_official.py` | Variant, protocol, no-clairvoyance and engine regressions |

`pokerbot/game.py`, `strategy.py`, `bots.py`, `opponents.py`, `benchmark.py` and
`legacy_protocol.py` are the historical two-card experiment. Their old tests can
still run, but they are not imported by the current bot or included in its archive.

## Submission artifact

`python -m tools.package` creates `dist/discard-holdem-submission.zip`, with
`bot.py` at the top level and the current v4 candidate modules. It also exports
`dist/discard-holdem-baseline.zip` directly from the tested v1 snapshot, refreshes
the previous runtime ZIP filename and creates a full source/reproducibility ZIP.
The packager enforces the 5 MB limit and verifies real protocol replies from the
archives without falling back to workspace modules, then runs each ZIP through
the supplied engine. No Unstop upload is automated.
