# Measured local results

All four local development phases are complete. Official rule/protocol integration
and verification on the organizer's runtime remain outstanding. No upload was made.

## Experimental conditions

Heads-up no-limit Hold'em, 1/2 blinds, 200-chip starting stacks reset every hand,
no rake. Each shuffled deck is played twice with bots swapping seats. These
settings are assumptions because complete tournament rules have not been supplied.

Development seed family: 110800 + match_index * 1009. Held-out family: 880000 +
match_index * 1009. The strategy was frozen before inspecting held-out results;
the report verifies that the current core files still match the recorded hashes.

## Phase progression

| Phase | Candidate | Matches | Hands | Wins | Draws | Losses |
|---|---|---:|---:|---:|---:|---:|
| 1: foundation | baseline | 32 | 12,800 | 28 | 0 | 4 |
| 2: range-aware | range | 40 | 16,000 | 35 | 0 | 5 |
| 3: adaptive development | adaptive | 48 | 19,200 | 46 | 0 | 2 |
| 4: held-out | adaptive | 80 | 32,000 | 78 | 0 | 2 |

The opponent sets grow between phases; raw win rates are not a controlled
comparison across all four rows. Phase 3 has a separate matched-seed comparison
against 48 range-bot matches, using six common seeds per opponent.

Adaptive minus range bot: **+0.0625 match points per match**
and **+1.0275 BB/hand**, averaging opponent types equally.
Approximate paired bootstrap 95% interval for the match-point difference:
[-0.020833333333333332, 0.125]. It includes zero; the limited
sample does not establish a statistically reliable match-point improvement.

## Frozen held-out league

| Opponent | W / D / L | BB/hand | Approx. 95% half-width | Match points / match |
|---|---:|---:|---:|---:|
| baseline | 8 / 0 / 0 | +0.4994 | 0.2258 | 1.000 |
| calling | 8 / 0 / 0 | +7.0552 | 0.5793 | 1.000 |
| tight | 8 / 0 / 0 | +0.5777 | 0.1234 | 1.000 |
| aggressive | 7 / 0 / 1 | +0.9170 | 0.4418 | 0.875 |
| random | 8 / 0 / 0 | +2.1856 | 0.4540 | 1.000 |
| equity | 8 / 0 / 0 | +2.1392 | 0.7049 | 1.000 |
| value | 8 / 0 / 0 | +1.2069 | 0.0991 | 1.000 |
| switching | 8 / 0 / 0 | +3.6166 | 0.4438 | 1.000 |
| shove | 8 / 0 / 0 | +3.5697 | 0.6231 | 1.000 |
| range | 7 / 0 / 1 | +0.7933 | 0.4045 | 0.875 |

Total: **78 wins, 0 draws, 2 losses across 80 matches and 32,000 hands**.
The league completed without illegal actions or crashes. Recorded budget fallbacks: 0.
The process was pinned to one logical CPU. League timing excludes subprocess I/O.

## Runtime integration checks

Persistent Python 3.11 subprocess, JSONL decisions and terminal events, one logical
CPU. Audit hooks reject filesystem writes, network socket operations and child
process creation inside the bot. These hooks are diagnostics, not an OS sandbox.

| Opponent | Hands | Transport-inclusive bank time | Peak working set | Errors |
|---|---:|---:|---:|---:|
| calling | 1000 | 43.761 s | 14.71 MiB | 0 |
| equity | 1000 | 27.005 s | 14.73 MiB | 0 |

Bank measurements include startup wait, serialization, response wait and terminal
messages; they exclude development-engine and opponent computation between requests.
This is local Windows/Python 3.11.9 evidence. It does not reproduce the organizer's
Linux CPU speed or certify its 1 GB/read-only/network sandbox.

## Correctness checks

- Python 3.11 suite: 38 tests, 0 failures, 0 errors.
- Exhaustive category counts: all 2,598,960 five-card hands match expected frequencies.
- Independent oracle: 20,000 additional seeded seven-card hands agree.
- Tests cover kickers, wheel straights, paired boards, full houses, all-in settlement,
  raise limits, duplicate cancellation, sampled-card exclusion, exhausted budgets,
  malformed JSON, duplicate requests, terminal actions and direct/adapter parity.

## Limits and next integration step

These are locally authored synthetic opponents. Some share policy code with our bot.
They are not a representative sample of tournament entrants. Neither positive chip
rates nor local match wins prove low exploitability or future tournament success.
The approximate intervals use whole matches and normal approximations; eight matches
per opponent still provide limited evidence. The official chip cap is unknown and
has not been substituted with an invented formula.

Next: map the official protocol, verify actual stack/betting rules and process lifetime,
and rerun legality/runtime tests in the provided environment. Until then the ZIPs
are development bundles rather than verified tournament submissions.
