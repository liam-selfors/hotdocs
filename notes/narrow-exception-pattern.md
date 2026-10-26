# Narrow Exception, Never Reopen the Boundary

_Working notes. Non-normative. The same move, applied independently at
least four times: `R-ASSEMBLE-010`'s `dependency_context` (`D35`),
`D16`'s `depends_on_guarantees` narrowing, `failure_detail`'s exclusion
from `requirement_results` (`D38`), and `VAR-TRUST-JUDGE-PROVENANCE`'s
criterion-kind scoping (`D39`). Started: 2026-10-26._

## The pattern

When a dependent needs **one more fact** from a dependency or
mechanism than an existing boundary currently allows through, the
answer is almost never "loosen the boundary." It's: add a new,
narrowly-scoped, separately-named field or mechanism **alongside** the
original, and leave the original's own meaning untouched.

- `spec-bundle-assembler`'s `R-ASSEMBLE-002` says a dependent gets a
  dependency's `interface/` content only, never `component.md`. When
  generation also needed a dependency's `Purpose` text, the fix wasn't
  to redefine what `R-ASSEMBLE-002` hands over — it was a new field,
  `dependency_context`, with its own requirement (`R-ASSEMBLE-010`)
  naming itself as the one explicit exception. `dependency_interfaces`
  stayed exactly what it always meant.
- `D16`'s guarantee narrowing is the same move one level up: instead of
  loosening "a dependent's blast radius includes any change to a
  dependency's types," it added a second, narrower relationship
  (`depends_on_guarantees`) a dependent can opt into *in addition to*
  the coarse default, which stays available and unchanged.
- `R-VERIFY-011`'s `requirement_results` is deliberately boolean-only,
  specifically to keep `generator`'s retry mechanism from ever seeing
  acceptance-criterion content. Adding `failure_detail` (`D38`) didn't
  touch that boundary — the new field lives on `criteria[]`, explicitly
  barred from ever reaching `requirement_results` or `retry_feedback`.
- `VAR-TRUST-JUDGE-PROVENANCE` doesn't loosen trust corpus-wide — it's
  scoped to exactly one criterion kind (`llm-judge`), leaving
  `compiled`/`generated-test` governed by the unconditional
  re-verification rule they always had.

## Why this beats the alternative

Loosening an existing boundary's *meaning* means every other place
that already relied on the old, narrower meaning now has to be
re-audited — did anything assume `dependency_interfaces` never carries
rationale? Does anything assume `requirement_results` is always
content-free? A new, separately-named field alongside the original has
no such blast radius: everything that already depended on the original
boundary keeps working exactly as before, by construction, because
nothing about it changed.

## Checklist

1. Is there an existing boundary (an exclusion rule, a coarse default,
   a content restriction) that the new need is tempting you to loosen?
2. If yes: can the new fact be added as its **own**, narrowly-named
   field or mechanism instead, living beside the original?
3. Does the new field's own requirement name itself as *the* explicit
   exception (the way `R-ASSEMBLE-010` does), so a future reader
   doesn't have to infer that the original rule still holds everywhere
   else?
4. Would anything existing need to change its own behavior because the
   original boundary now means something different? If the honest
   answer is "no, nothing changes" — you've done it right.

## A related, smaller discipline: don't let a name collide with itself

Two of this session's own cleanup efforts (`component_doc_words` vs. the
`SpecBundle` type, and `cache_hit` meaning two different scopes before
`D39`'s rename) both trace to the same root mistake: reusing a word for
a narrower or broader concept than its existing meaning, rather than
picking a more specific name. Before naming a new field or dimension,
grep the corpus for the word you're about to reuse — if it already
means something at a different scope, a few extra characters in a more
specific name is cheaper than a future rename across a dozen files.
