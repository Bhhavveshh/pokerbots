# Discard Hold'em Pokerbot

Python 3.11 bot for the supplied Pokerbots **Discard Hold'em** competition.
Standard library only; no runtime installation, writes, sockets or subprocesses.
The competition entry point is `bot.py`.

The four improvement phases are tracked in [IMPROVEMENT_LOG.md](IMPROVEMENT_LOG.md).
Immutable strategy snapshots and matched-seed comparisons live in `experiments/`
and `reports/improvements/`. Tracking data and final fresh-seed evaluation are
reported separately, including unsuccessful changes.

**Default release: v1 baseline**, with the best observed fresh-panel result:
63/80 wins (78.75%) versus the v4 candidate's 60/80 (75%). The difference is
statistically inconclusive. `bot.py` and the submission ZIP now run byte-exact v1.
The release identity and file hashes are in `experiments/release.json`.

V4 remains available in its immutable snapshot, a separate experimental ZIP and
`pokerbot/experimental_agent.py` for later development. Historical results are
preserved; promoting v1 does not rewrite the experiment or claim universal superiority.

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
python -m tools.experiments evaluate reproduce-baseline --version v1 --opponents reference frozen_v1 equity polar --matches 20 --seeds improve-final-v1 --cpu 0
python -m tools.validate_cfr
python -m tools.improvement_report
python -m tools.build_report
python -m tools.package
```

The first command reproduces the frozen baseline panel under a new report label.
Use a different label and `--version v4` to reproduce the historical candidate.
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

The experimental v4 agent adds consistent flop/discard selection, an offline
preflop ordering and optional exact-river, response-tree and CFR models. Its real
CFR implementation passes known finite-game checks, but the one-bet river model
performed worse in full matches and remains an experiment. It is not imported by
the default v1 runtime. Compare frozen v1/v4 policies using `tools.experiments`;
see [IMPROVEMENT_LOG.md](IMPROVEMENT_LOG.md) for retained and rejected changes.

## Source map

| File | Current role |
|---|---|
| `bot.py` | Top-level submission entry point; disables bytecode writes |
| `pokerbot/protocol.py` | Official protocol 1.0 lifecycle, validation and replies |
| `pokerbot/agent.py` | Triple/pair beliefs, equity, action EV, adaptation and time |
| `pokerbot/discard.py` | Flop-only keep policy, draws and soft discard evidence |
| `pokerbot/cards.py` | Fast standard hand evaluator and testing oracle |
| `pokerbot/experimental_agent.py` | Editable v4 experiment; excluded from production ZIP |
| `pokerbot/preflop.py`, `preflop_data.json` | Experimental offline equity ordering |
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
`bot.py` at the top level and only the selected v1 runtime modules. The aliases
`discard-holdem-baseline.zip` and `pokerbot-runtime.zip` contain the same bytes.
`dist/discard-holdem-experimental-v4.zip` preserves the historical v4 candidate;
`pokerbot-source.zip` contains the source, snapshots, tests and evidence for later work.

The packager enforces the 5 MB limit, verifies real protocol replies directly from
both versioned ZIPs and tests both through the supplied engine. No Unstop upload
is automated. The organizer server sandbox remains unverified.
