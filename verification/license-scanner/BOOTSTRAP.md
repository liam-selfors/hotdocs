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
