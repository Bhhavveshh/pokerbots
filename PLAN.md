# Four sequential improvement phases

The supplied Discard Hold'em rulebook, protocol and engine supersede the original
ordinary Hold'em assumptions. Source audit: `official/README.md`.

The current default release is v1, promoted at the user's request after the fresh
comparison. `experiments/release.json` records its exact identity. V4 and the
four-phase measurements below remain preserved for later development.

1. **Diagnose and align decisions.** Freeze v1 and all tracking opponents. Run
   direct ablations on a fixed development panel. Make flop equity and the actual
   discard use the same retained pair. Test public-discard inference and opponent
   adaptation rather than assuming every feature helps.
2. **Improve bounded expected value.** Generate preflop equity ordering for all
   1,755 suit-equivalent triples under flop-only discard policies. Separately test
   exact weighted river enumeration and a fold/call/re-raise response model. Keep
   only candidates supported by measured match points and chip results.
3. **Test actual game-theoretic solving.** Implement vanilla CFR on a finite
   one-bet river game. Validate the known Kuhn value and exact best responses.
   Construct both players' ranges from public information, then select the actual
   hero bucket after solving. Compare the prototype in full official matches.
   A mathematically correct restricted solver is not automatically a stronger bot.
4. **Freeze, validate and deliver.** Lock the chosen production version before
   fresh seeds. Compare baseline and final in 80 complete matches each, including
   two independent policies. Run full Stage 1/2 guarded matches, correctness tests,
   verify ZIP imports and delivery, then publish the source to the repository.
   Fresh validation did not confirm the gain. We preserved that result and
   exported the tested v1 baseline as a conservative submission alternative.

## Measurement rules

- `IMPROVEMENT_LOG.md` and `experiments/decisions.json` record selections, rejected
  candidates, win rates, likely mechanisms and uncertainty. An increase is never
  assumed in advance. Tracking data is explicitly used for development.
- Normal official timing stays enabled in every performance match. Each match
  and its children use one logical CPU. Timed sample cutoffs can change the RNG
  path even with fixed seeds; logic-only fixed-work replay is separately labelled.
- Fresh final seeds are never used for subsequent tuning. Whole deal-seed blocks
  across opponents are resampled for paired intervals; hands are not treated as
  independent observations. Synthetic opponents do not represent the field.
- Public dead-card information always blocks cards. Disabling a heuristic about
  why the opponent discarded a card does not disable this correctness rule.
- No duplicate-deal detection, cross-leg persistence, runtime writes, networking,
  subprocesses or runtime installation. Only Python 3.11 standard libraries used.
- Full-game equilibrium solving and a neural architecture would be overengineering
  for the current time bank and evidence. The smallest tested improvement wins.

Current evidence is in `RESULTS.md` and `reports/improvements/`. The original
Discard Hold'em rebuild remains in `reports/discard_holdem/`; earlier two-card
reports at the root of `reports/` are historical, not competition evidence.
