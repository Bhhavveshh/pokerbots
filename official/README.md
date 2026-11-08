# Organizer materials

`Starter_Kit/` was extracted from the user-supplied ZIP
`aa53d854-c36c-41e4-9c64-4e0cba64d04d.zip`. Its contents are unchanged. The three
top-level user PDFs are byte-identical to the named PDFs in this kit:

| Supplied PDF | Kit document | SHA-256 |
|---|---|---|
| `dc23ff53-f442-498a-ba62-8c16f559469f.pdf` | `problem_statement.pdf` | `3be1c27c19081ca8454cd84d3a2f02f35fca8ac068c757a68af99a9d2fa0e3a9` |
| `cfad975a-e1b5-450d-8343-5273c6dabdb8.pdf` | `rulebook.pdf` | `df964016c030f5ab55cc224b47313c7b0e8b76de924ff7a79b3773b9aaacf346` |
| `4e7838aa-887f-4a61-be4b-c3dcf9ba1725.pdf` | `protocol_specification.pdf` | `b99c25e89e9065170931d481614e1d0e16d34800786d5b72f413a9487fb604fa` |

The organizer permits reusing supplied material (Rulebook 10.1). Attribution stays
here; the organizer's engine and starter opponents are not claimed as our work.
The submitted bot uses our own evaluator and strategy, and imports no engine code.

## Authoritative rules that supersede the initial prototype

- Three initial hole cards, with one simultaneous exposed discard after flop
  betting, even when all-in. Keep only two hole cards for showdown.
- Blinds 1/2, 200 chips reset each hand, heads-up no-limit.
- Four bets/raises per street; the big blind consumes one preflop raise.
- A match is two separate legs. Processes restart each leg and cannot share state
  or attempt to identify duplicate deals. Deals are not replayed within a process.
- Stage 1: 200 hands per leg, 30 s bank, 90 s wall limit. Stage 2: 500 hands per
  leg, 75 s bank, 225 s wall limit. Both have a 5 s reply limit and startup grace.
- Match points are primary. The chip cap is applied to each MATCH's net result,
  then divided by total scheduled hands; C=400/1000 in Stage 1/2 (provisional).
- Single `bot.py` or ZIP with `bot.py` at root, at most 5 MB. No writes, sockets,
  subprocesses, runtime installation or out-of-band state in the submitted bot.
- Respond only to `action_request` and `discard_request`; notifications are silent.
  Ignore unknown types/fields and exit on `match_end`.

All three PDFs (21 pages total), the kit README, `engine.py`, `bot.py`, and the
example random opponent were read. Critical rule/protocol tables were also
rendered for visual verification. No material contradiction between the supplied
runner and the documents was found in the implemented paths. Documents prevail
over the kit if a discrepancy is discovered (Rulebook 1.3).
