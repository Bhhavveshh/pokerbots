# Rebuild against the supplied Discard Hold'em rules

The initial ordinary Hold'em assumptions are superseded. Canonical organizer
materials, precedence and hashes are recorded in `official/README.md`.

## Four sequential phases

1. **Audit and integration:** read all three PDFs/kit files, retain the verified
   evaluator, replace the invented protocol, and validate a real match with the
   unmodified supplied engine. Preserve the historical prototype for provenance.
2. **Variant-aware strategy:** three-card preflop/flop beliefs; flop-only simulated
   discard policies; compare all three real discard choices on common samples;
   rebuild conditioned pair ranges after exposed discards; block every known dead
   card; obey the four-raise cap using engine-supplied legality.
3. **Evaluation:** seeded synthetic opponents and direct ablations; separate
   development (`discard-dev-*`) from frozen evaluation (`discard-heldout-v1-*`).
   Report match points first, chip results, exact capped score and uncertainty.
   Do not tune parameters on the frozen evaluation seeds.
4. **Runtime and delivery:** full 400/1000-hand official matches with clocks and
   resource audit guards, Python 3.11 checks, source/diff review, and a <=5 MB ZIP
   with bot.py at root. Verify the packaged modules through the official runner.

## Decisions and limits

- Use the supplied engine as the test authority; never rewrite its rules to fit
  our bot. Documents prevail if a discrepancy is found (Rulebook 1.3).
- A discard is selected from a flop, never from a simulated completed board. The
  simulation can sample future cards to estimate equity, but a simulated policy
  sees only information available at its decision time.
- Do not detect duplicate deals or share state between legs. Model memory is
  confined to one process/leg and resets on init.
- Keep standard-library-only heuristics and bounded sampling. Full-game CFR and
  neural training remain deferred; correctness and reproducible official-engine
  evidence take priority over additional architecture.
- Synthetic opponents share some components. Results near zero against the
  reference/no-signal policies do not establish strategic superiority.
- Provisional time/score values may change; recheck organizer announcements before
  submission. Local Windows tests cannot certify the server's Linux sandbox.

`RESULTS.md` and `reports/discard_holdem/` contain current evidence. The old JSON
files at `reports/` root and the historical two-card harness are not competition
performance evidence. The runtime archive excludes historical modules entirely.
