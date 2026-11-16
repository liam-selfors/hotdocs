# Bootstrap Account: `secret-scanner`

First real cold-generation of this component, via the self-hosted
`gen/generator/generator.py` (`D42`), in a single real `generate()`
call that passed verification on the first try.

Before this attempt, `D53` proactively declared
`VAR-SECRET-PATTERNS-PATH` — `secret-scanner`'s own spec explicitly
mirrors `license-scanner`'s reference-corpus sourcing text
(`R-SECRET-001` cites `R-LICENSE-001` by name), and a real
`license-scanner` candidate had already defaulted to `.hotdocs/`
before `VAR-LICENSE-CORPUS-PATH` existed to correct it (`D51`). Adding
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

## `D163`/`D164`: regenerated with `gate_version` and CLI coverage

Regenerated so a provenance key can read this scanner's version
without running a scan (`R-SECRET-010`), and with its CLI covered
(`R-SECRET-011`, `D162`). Nine rounds, landing at 14 of 14,
`mutation_score=0.86`. Behaviorally every criterion passed from round
2 on; the rest of the rounds were spent on what the spec left open:

- A stand-in placed under `gen/` is itself scanned, and one embedding
  a temporary path tripped the entropy heuristic; `http.server`'s bind
  took 35 seconds resolving a host name and timed a test out.
  `interface/library.md` now forbids high-entropy strings in stand-ins
  and routes the webhook only through `urllib.request.urlopen`.
- The live and regenerated implementations disagreed on the entropy
  heuristic's candidate length and `rule_id`; `R-SECRET-001` now pins
  it exactly, plus one match per secret, UTF-8 text files only, and no
  `__pycache__` (a compiled `.pyc` was scanned and flagged).
- A match's `file` form, a relative `--files` path, the precommit
  default file set, a relative pattern-database path, and the
  webhook-failure categories were all left open and are now stated.
- `mutation_score` swung between 0.73 and 1.0 across rounds with
  every criterion passing, depending on which tests were authored —
  the oscillation `D137` already recorded. Each low round's survivors
  were checked; the ones that marked a real unstated scenario were
  added to the criteria.

An earlier `AC-SECRET-005` edit in this series required that a cache hit read no
file at all, impossible since computing the key reads the files; it
now asserts only what a hit observably returns.

The original hand-written `test_secret_scanner.py` was removed: it read
results by attribute, which the corpus's dual-access convention never
required, and no consumer in `gen/` does. The generated criterion tests
supersede it.
