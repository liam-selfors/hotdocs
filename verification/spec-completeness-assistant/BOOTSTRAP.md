# Bootstrap Account: `spec-completeness-assistant`

Cold-generated, not hand-written — a real model call, through a real
`generator` dispatching through a real `llm-endpoint`, from this
component's own assembled spec bundle, with real `test-author`-authored
criterion tests and real `verifier-orchestrator` mutation scoring.
Landed at 8 of 8 `generated-test` criteria passing (the two `llm-judge`
criteria, `AC-ASSIST-004`/`005`, are `skipped` with no judge model
configured), `mutation_score=0.81`, after seven rounds spanning four
decisions (`D155`–`D157`, `D160`) plus one gate fix (`D158`/`D159`).

## Phase 1: what the spec never pinned (`D155`–`D157`)

Early rounds failed on behavior the spec left open: whether a
hard-fail lint finding stops the run (`D155`: it does, and nothing
else is called), which dependency functions are called and in what
order, with what signature (`D156`: `interface/library.md` now lists
each call), and what "degraded mode" means for the `generator` call
(`D157`: no model, no model call of any kind, and the preview is the
hint bundle itself).

## Phase 2: a mutation gate that hung (`D158`/`D159`)

A round stalled for 45 minutes with the machine under memory pressure.
The cause was in `verifier-orchestrator`, not here: a mutant that
turned a CLI-parsing loop's `i + 1` into `i - 1` never terminated, and
`_run_pytest` had no timeout. That fix (`R-VERIFY-014`) landed in the
gate first; this component's score was unchanged by it, which ruled
out timeouts as the cause of the low score.

## Phase 3: coverage, not correctness (`D160`)

With every behavioral criterion passing, `mutation_score` sat at 0.47.
Sixteen survivors fell in two clusters: the CLI (no requirement ever
covered `hotdocs assist`, the fourth component with that gap) and
everything around the model calls, which no test could reach because
the spec never said what the model is asked to return.
`R-ASSIST-009`/`010` closed both, raising the score to 0.76. Of the
next ten survivors, six were equivalent mutants; the other four were
small gaps (a flag's value as the next argument, `--model` reaching
`assist`, the score in text output, an empty rationale) closed in the
same decision. The next round landed at 0.81.
