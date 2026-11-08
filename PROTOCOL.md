# Development protocol v1

**This is our adapter contract, not the organizer's protocol.** A persistent
Python process reads one UTF-8 JSON object per line and writes one JSON response
per line, flushing immediately. Run `python -B bot.py`. Debug failures go to
stderr. Runtime execution requires only standard Python 3.11.

## Reset before each opponent match

```json
{"type":"reset","seed":42,"time_bank":60,"expected_hands":400}
```

Response: `{"ready":true,"protocol":"development-v1"}`. Use 1000 expected hands
for a 500-duplicate-deal match. Reset creates fresh opponent statistics and RNG.
Default configuration is seed 0, 60 seconds, 1000 hands.

## Request a decision

```json
{"type":"act","remaining_seconds":59.5,"observation":{"hand_id":0,"player":0,"button":0,"hole":["As","Kd"],"board":[],"stacks":[199,198],"pot":3,"street":0,"contributions":[1,2],"call_cost":1,"min_raise_to":4,"max_raise_to":200,"big_blind":2,"history":[]}}
```

Response is `{"action":"fold"}`, `{"action":"check"}`, `{"action":"call"}`, or
`{"action":"raise","amount":5}`. **Raise amounts are totals on the current
street**, including chips already committed on that street. They are not raise
increments or total contributions across the hand.

- Players are seats 0 and 1. `button` identifies the small blind in heads-up play.
- Streets: preflop=0, flop=1, turn=2, river=3.
- Cards accept rank/suit strings or integers 0..51 (`rank*4+suit`, ranks
  `23456789TJQKA`, suits `cdhs`). No opponent private cards are accepted.
- `pot` includes all chips already committed, including the bet facing us.
- `contributions` contains each player's current-street contribution.
- `call_cost` is the actual capped cost, not the uncapped outstanding bet.
- Both raise bounds must be null when a raise is illegal. A short all-in may
  have equal minimum and maximum bounds.
- `remaining_seconds` is optional. It can reduce the internal bank but never
  increase it. The bot reserves time for communication and integration overhead.
- Hand IDs must increase between hands. Within a hand, hole cards, player and
  button stay fixed; public history is append-only and board cards are a prefix
  of subsequent boards. An identical repeated request returns its cached action.

Every public action in `history` has this shape:

```json
{"player":0,"street":0,"kind":"raise","amount":5,"paid":4,"pot_before":3,"call_cost":1,"board":[]}
```

`paid` is the incremental chip payment. `amount` is zero for check/call/fold.
Include both players' actions. Blinds are represented by the observation's chips,
not as action events. Only information actually revealed may appear in `board`.

## Finish every hand

```json
{"type":"hand_end","hand_id":0,"player":0,"board":[],"history":[{"player":0,"street":0,"kind":"raise","amount":5,"paid":4,"pot_before":3,"call_cost":1,"board":[]},{"player":1,"street":0,"kind":"fold","amount":0,"paid":0,"pot_before":7,"call_cost":3,"board":[]}]}
```

Response: `{"ok":true}`. Send the final public history even if the bot has no more
decisions. Otherwise final folds/calls are missing from opponent learning. Use
the actually revealed board; do not send the undealt runout after a fold.
Duplicate identical terminal messages are idempotent.

## Failure behavior

Malformed messages return `{"error":"invalid_request"}`. Lines longer than
65,536 bytes return `{"error":"request_too_large"}` and are drained before the
next request. A strategy exception on a valid observation logs its exception
class to stderr and returns a legal check/fold fallback.

The official adapter must eventually map the organizer's observations, action
bounds, terminal events, process lifecycle and time-bank units to this core. If
the organizer restarts the process on every action, our in-memory learning cannot
persist without an explicitly supported state field.
