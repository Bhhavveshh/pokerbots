# Report scopes

**Current competition evidence is in `discard_holdem/`.** Those reports use the
supplied Discard Hold'em engine, official protocol, two fresh-process legs,
exposed discards, raise cap, and live tournament clocks.

The existing JSON files directly in this directory are historical experiments
for ordinary two-card Hold'em and an invented development protocol. Their win
rates, timing results and model hashes DO NOT validate the competition bot. They
are retained for provenance, not combined with current results. `evaluator.json`
is still a useful historical evaluator check; current tests also independently
compare the evaluator against the organizer's implementation.
