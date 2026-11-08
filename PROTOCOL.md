# Official protocol 1.0

The authoritative source is `official/Starter_Kit/protocol_specification.pdf`.
This file documents our adapter implementation, not a replacement specification.
The earlier invented `reset`/`act`/`hand_end` interface is historical and is not
accepted by the submission entry point.

Run `python3.11 bot.py`: one UTF-8 JSON object per line on stdin; exactly one
flushed reply for `action_request` or `discard_request` only. All informational
messages and unknown types/fields are silent. Exit after `match_end`.

| Incoming type | Effect | Reply |
|---|---|---|
| `init` | Reset leg-local model/RNG; read hand count and bank | none |
| `new_hand` | Record seat and three private cards; clear hand beliefs | none |
| `action_request` | Ingest public history and choose a legal action | `action` |
| `discard_request` | Choose one of three cards using the flop | `discard` |
| `discard_result` | Store remaining pair and public opponent discard | none |
| `hand_result` | Ingest final public actions, including terminal folds/calls | none |
| `notice` | Informational; next engine state remains authoritative | none |
| `match_end` | Exit this process; no state written anywhere | none |
| unknown | Ignore for forward compatibility | none |

```json
{"type":"action","action":"check"}
{"type":"action","action":"call"}
{"type":"action","action":"fold"}
{"type":"action","action":"raise","amount":12}
{"type":"discard","card":"7c"}
```

Raise amounts are **totals on the current street**, not increments. A `call`
history entry also carries a street total. We reconstruct actual payments using
each actor's previous street contribution, including blinds on preflop. No amount
is sent for check/call/fold replies. Card strings use the organizer's notation;
internal integer suit order is private and converted consistently.

`legal_actions`, `min_raise`, `max_raise` and `raises_left` are authoritative. A
raise can be absent even when `raises_left > 0`, notably against an all-in. Short
all-ins can have equal minimum and maximum bounds. Both discard requests must be
answered even if no further betting is possible.

Both discard choices are simultaneous. Before `discard_result`, the strategy has
no access to the opponent's chosen discard. Afterwards the exposed card is used
as a blocker and as soft range evidence. Original dealt cards that we discarded
remain blocked as well: the board was fixed before either discard.

We retain only in-memory state for the current leg. There is no duplicate-deal
matching, persistent storage, environment-based signalling or cross-leg state.
The official runner starts fresh processes for both legs.

Per-request deadlines are bounded well below the 5 s reply limit, with an overall
reserve based on reported bank remaining. Request validation and output legality
checks catch integration mistakes. On a valid decision boundary, an exception is
logged to stderr and a legal check/fold or lowest-card discard is returned. Local
validation rejects **any** candidate stderr, corrections or forfeits, so these
fallbacks cannot conceal strategy failures in reported matches.
