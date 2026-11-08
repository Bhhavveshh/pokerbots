# Discard Hold'em: current measured results

The bot was rebuilt from the three supplied PDFs and unchanged starter kit. The
original two-card Hold'em policy/protocol is no longer the competition entry point.
Its earlier **78/80** result is obsolete for this variant and is not reused here.

## What changed

- Official protocol 1.0, including silent notifications and process exit on `match_end`.
- Three-card preflop/flop decisions, simultaneous discard requests even while all-in,
  and post-discard pair ranges with both discards removed from future cards.
- Common-sample discard comparison and soft inference from the public opponent discard.
- Four-raise cap/short-all-in bounds taken from the engine's legal actions.
- Two separate legs and per-leg timing; no cross-leg memory or duplicate identification.
- Exact official capped-match score, replacing the old unknown-cap assumption.

## Validation method

All performance runs use the unmodified supplied `engine.py`, Python 3.11.9, its
normal time banks, startup grace, per-reply deadlines and wall limits. A metrics
wrapper records outcomes/charged clocks; it does not change game or timing logic.
All seven kit files were checked byte-for-byte against the supplied ZIP.

Each Stage 1 match is two fresh-process legs of 200 hands, with duplicate cards
and seats swapped by the supplied runner. Development uses `discard-dev-*` seeds.
The frozen evaluation uses fresh `discard-heldout-v1-*` seeds, four complete
400-hand matches per opponent. No runtime code changed during or after that run.
The report verifies the current runtime/engine hashes against the frozen snapshot.

The process and children were pinned to one logical CPU for these runs. Local
opponents are synthetic and some share our strategy code; this is not a sample
of tournament entrants. Intervals below are approximate normal intervals over
whole matches and are particularly uncertain with just four matches per opponent.

## Phase results

| Run | Matches | Hands | Wins | Draws | Losses |
|---|---:|---:|---:|---:|---:|
| Development | 12 | 4,800 | 10 | 0 | 2 |
| Frozen held-out | 32 | 12,800 | 26 | 0 | 6 |

## Frozen opponent results

| Opponent | W / D / L | BB/hand | Approx. 95% half-width | Match points / match |
|---|---:|---:|---:|---:|
| starter | 4 / 0 / 0 | +19.6487 | 1.5876 | 1.000 |
| tight | 4 / 0 / 0 | +0.7466 | 0.3361 | 1.000 |
| aggressive | 4 / 0 / 0 | +2.8869 | 1.6802 | 1.000 |
| shove | 4 / 0 / 0 | +6.4416 | 1.3259 | 1.000 |
| switching | 4 / 0 / 0 | +8.6225 | 0.5295 | 1.000 |
| reference | 1 / 0 / 3 | -0.1394 | 0.1418 | 0.250 |
| no_signal | 1 / 0 / 3 | -0.0122 | 0.7474 | 0.250 |
| fast_discard | 4 / 0 / 0 | +0.3909 | 0.3259 | 1.000 |

Overall: **26 wins, 0 draws, 6 losses**,
32 matches and 12,800 hands; zero candidate corrections,
forfeits or stderr errors. BB/hand is chips divided by hands and by the 2-chip big blind.
The exact capped score over this synthetic test schedule is +0.6377 chips/hand.

`starter` is the organizer's check/call + lowest-rank-discard bot. `tight`,
`aggressive`, `shove`, and `switching` are our seeded heuristic stress opponents.
`reference` uses our range/equity policy with adaptation, discard optimization
and discard inference disabled. `no_signal` disables only discard inference;
`fast_discard` disables only sampled discard optimization. They still block all
known dead cards. Those comparisons are direct head-to-head ablations, not
independent implementations or proof of any feature's value.

**Weakness:** results against the range-aware reference and no-signal policy are
not convincing. The sample is small, and it does not establish an advantage over
these stronger related policies. The large profits against passive opponents
must not be generalized to the tournament field. No equilibrium or exploitability
guarantee is claimed. No parameters were tuned against these held-out seeds.

## Full-length guarded runtime checks

Audit hooks reject writes, socket operations and child-process creation inside
the bot. The authoritative runner's clocks remain enabled. Audit hooks and
affinity are local diagnostics, not a substitute for the organizer sandbox.

| Stage / opponent | Hands | Leg 1 charged | Leg 2 charged | Bank per leg | Peak working set |
|---|---:|---:|---:|---:|---:|
| 1 / starter | 400 | 4.782 s | 3.754 s | 30 s | 14.25 MiB |
| 2 / starter | 1000 | 18.920 s | 16.560 s | 75 s | 14.61 MiB |
| 2 / reference | 1000 | 8.574 s | 5.181 s | 75 s | 14.45 MiB |

Charged time is exactly the runner's measure: sending a request through receipt
of its reply after applying the official startup grace. Each discard is charged
too. Engine/opponent work between requests is not part of the bot's bank.
Every recorded guarded match completed all scheduled hands with zero candidate
notices, forfeits or stderr. The server's CPU speed/OS and upload portal remain
unverified; the local machine runs Windows, not the organizer's Linux sandbox.

## Correctness

- Python 3.11 suite: **54 tests**, zero failures/errors.
- Current variant tests cover all-in discard, public blockers, conditioned pair
  ranges, raise-cap bounds, protocol silence/exit, terminal history, fresh-leg reset,
  and guards against choosing a discard using a simulated turn or river.
- 1,200 additional seven-card hands agree with the organizer's independent evaluator.
- Historical evaluator checks covered every five-card category frequency and
  20,000 further seven-card oracle comparisons; the evaluator itself was retained.
- Other retained tests concern the historical two-card implementation and are not
  counted as evidence for Discard Hold'em strategic strength.

## Artifacts and remaining work

Run `python -m tools.package` to create `dist/discard-holdem-submission.zip`
(bot.py at root, standard library only, below 5 MB), verify imports from the ZIP
and play a packaged-bot match through the supplied runner. Its manifest records
hashes and the package test. A separate source ZIP includes organizer materials,
tests, tools and both historical/current reports with their scopes documented.

No Unstop submission was made. Before the deadline, check organizer amendments
to provisional values, verify the actual server sandbox if offered, and improve
evaluation against independently designed stronger opponents. The bot is a tested
competition-compatible local implementation, not an established winning strategy.
