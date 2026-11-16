# Bootstrap Account: `license-scanner`

First real cold-generation of this component, via the self-hosted
`gen/generator/generator.py` (`D42`), through two real `generate()`
calls.

**Call 1** produced a genuinely well-reasoned candidate — correct
9-token k-gram tokenization/hashing, correct severity-vs-confidence
notification split (`R-LICENSE-003`), a bounded, never-retried webhook
call — but defaulted its reference-corpus lookup path to
`.hotdocs/license_corpus.json`. `SPEC_GUIDELINES.md` §1 forbids any
gate's pass/fail decision from depending on `.hotdocs/` content
(gitignored, local-only, observability-only) — and this corpus's
content directly determines `blocked`. Real gap, same root cause as
`D46`/`D49`: `SPEC_GUIDELINES.md` is never part of any `SpecBundle`.
Fixed with a new `VAR-LICENSE-CORPUS-PATH` (`D51`). Not swapped in.

**Call 2**, with that fix in place, correctly reads the corpus path
from `VAR-LICENSE-CORPUS-PATH` only, with no `.hotdocs/` fallback, and
even includes a resilient in-process fallback `cache-manager` stand-in
for the (here, never-hit) case where the real dependency can't be
located on disk. Verified against all 8 directly-testable
`AC-LICENSE-*` criteria for real (10 tests — `AC-LICENSE-003`'s
"notified independent of risk_tier" claim covers two distinct real
behaviors, `003b`/`003c`). `AC-LICENSE-007` (preserving an original
flagged result across a later clean retry) is not independently
testable at this component's own level — it depends on
`provenance-writer`/`.hotdocs/attempts/`, neither of which exist yet.
Swapped in.

Test fixtures construct a reference-corpus entry by running the
candidate's own real `_document_kgram_hashes()` against known
`gen/<slug>/` content first, then embedding those exact hashes as the
entry's `hashes` list — this tests the scoring/notification/caching
logic against a guaranteed match without reimplementing the
tokenizer/hashing algorithm by hand in the test suite itself.

## `D163`/`D164`/`D165`: regenerated with `gate_version` and CLI coverage

Regenerated so a provenance key can read this scanner's version
without running a scan (`R-LICENSE-008`), and with its CLI covered
(`R-LICENSE-009`, `D162`). Seven rounds, landing at 13 of 13,
`mutation_score=0.88`. Every failure traced to a gap outside the
candidate's control:

- Round 1 crashed inside `verifier-orchestrator`, which turned
  `AC-LICENSE-003b` into `AC-LICENSE-003B`; fixed there first
  (`R-VERIFY-016`).
- Nothing defined how a `VAR-*` declaration maps to an environment
  variable; the candidate and three tests used four different
  conventions. The glossary now defines it (`D164`).
- The reference-corpus file format and window hashing were never
  written down; now `interface/data/ReferenceCorpus.md`.
- Tests' stand-ins for `cache-manager` kept missing a name the
  candidate used (`CacheKey`, then `CachedResult`, then a timestamp
  helper), each failure swallowed by the candidate's own
  never-fail-on-cache posture. `interface/library.md` now names
  exactly the four `cache-manager` names used and forbids any other.
- One candidate wrote its file one directory too deep; `generator`
  now strips that redundant prefix (`D165`).

The original hand-written `test_license_scanner.py` was removed: it
called a private helper of the previous implementation and read
results by attribute, which the corpus's dual-access convention never
required. The generated criterion tests supersede it.
