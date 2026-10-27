# Bootstrap Account: `secret-scanner`

First real cold-generation of this component, via the self-hosted
`gen/generator/generator.py` (`D58`), in a single real `generate()`
call that passed verification on the first try.

Before this attempt, `D69` proactively declared
`VAR-SECRET-PATTERNS-PATH` — `secret-scanner`'s own spec explicitly
mirrors `license-scanner`'s reference-corpus sourcing text
(`R-SECRET-001` cites `R-LICENSE-001` by name), and a real
`license-scanner` candidate had already defaulted to `.hotdocs/`
before `VAR-LICENSE-CORPUS-PATH` existed to correct it (`D67`). Adding
the analogous var up front avoided spending a billed call to
rediscover the identical, predictable gap.

The real candidate correctly reads the pattern database path from
that var only, with no `.hotdocs/` fallback anywhere, confirming the
proactive fix worked. All 10 directly-testable `AC-SECRET-*` criteria
pass for real (12 tests — `AC-SECRET-004`'s risk-tier-independent
notification claim covers three distinct real behaviors,
`004`/`004b`/`004c`). `AC-SECRET-009` (an original flagged result must
survive a later clean retry) is not independently testable at this
component's own level, same as `license-scanner`'s `AC-LICENSE-007` —
it depends on `provenance-writer`/`.hotdocs/attempts/`, neither of
which exist yet.

The entropy-threshold test (`AC-SECRET-010`) uses two real 24-character
strings found by brute-force random search and measured against the
candidate's own `_shannon_entropy()` function — one at ~4.0016
bits/char, one at ~3.9906 — rather than hand-constructing strings and
hoping they land on the right side of the threshold.
