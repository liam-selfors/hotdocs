# Bootstrap Account: `component-gate-runner`

Cold-generated, not hand-written — a real model call, through a real
`generator` dispatching through a real `llm-endpoint`, from this
component's own assembled spec bundle, with real `test-author`-authored
criterion tests and real `verifier-orchestrator` mutation scoring.
The last unbuilt component in this corpus. Landed on its second round
at 13 of 13, `mutation_score=0.88`.

## Before the first build (`D163`, `D166`)

The spec was audited against what its dependencies actually expose
before any generation was spent. That audit found the larger defect
first: nothing this component wrote could ever have satisfied `hotdocs
verify`, because `provenance-tracker` computed its own
`spec_bundle_hash` and supplied empty `gate_versions`. `D163` fixed
that across five components with one canonical provenance key owned by
`provenance-checker`. `D166` then rewrote this spec: an exact dependency
call list, a result that can say why it is blocked, a judge contract,
CLI coverage, and a rule that only a hit recording a passing attempt
short-circuits, so a failed attempt can always be retried.

## Round 1

Every criterion failed, for three reasons. Eleven failed before any
test ran: `license-scanner` and `secret-scanner` both expose a function
named `scan`, and `test-author`'s fake-arity check keyed signatures by
bare name, so a correct fake of one was rejected against the other's
arity — fixed in `test-author` (`R-AUTHOR-020`). The candidate also
loaded `llm-endpoint` on a path that never calls it, and built a
`ProvenanceInputs` class the spec never named; `interface/library.md`
now requires loading each dependency only when it is first called and
using no name beyond its list.

## Round 2

13 of 13, `mutation_score=0.88`. Swapped in.

## `D170`: the sealed path writes a sealed manifest

`R-GATE-007` rewritten: a component is sealed when `provenance-checker`'s
`current_sealed_key` returns a key (this component no longer reads
`component.md`); it re-runs the characterization tests, runs both scans,
and then always writes a sealed provenance manifest through
`provenance-writer`'s `write_sealed_provenance`, passing or failing, so
the owner and the verdict are on file. Regenerated; the first run was
cut off by the model backend's usage limit (no result), and the second
landed at 13 of 13 criteria with `mutation_score` 0.94, no spec change
between them. Its suite is now 33 tests.
