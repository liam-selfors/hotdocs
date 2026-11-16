# Bootstrap Account: `provenance-tracker-ui`

Cold-generated, not hand-written — a real model call, through a real
`generator` dispatching through a real `llm-endpoint`, from this
component's own assembled spec bundle, with real `test-author`-authored
criterion tests and real `verifier-orchestrator` mutation scoring.
Landed at 9 of 9 criteria passing, `mutation_score=0.95`, after six
rounds spanning two decisions (`D154`, `D161`) plus one gate fix
(`D158`/`D159`).

## Phase 1: a spec that could not be built as written (`D154`)

The original spec asked for a static page that also rendered
`check_readiness`'s live result, querying the committed corpus graph
in the browser through DuckDB-WASM and its `duckpgq` extension, served
by `hotdocs track ui serve`. Those requirements could not all hold:
`check_readiness` is Python and may need a model call, which a static
page cannot make. Rebuilt as a build-time snapshot: `hotdocs track ui
build` calls `check_readiness` once, reads the corpus graph and attempt
records, and writes one self-contained `index.html` that opens from
`file://`. The first round on the new spec passed 7 of 9; the next
fixed fixture ambiguities (a stand-in `provenance-tracker` must provide
both functions it is called through; `__pycache__` is not a write).

## Phase 2: a mutation gate that hung (`D158`/`D159`)

Round 3 never finished: one mutant in a CLI-parsing loop never
terminated, and `verifier-orchestrator` had no timeout. That gate was
fixed first, then this component re-run.

## Phase 3: a self-contradiction and an untested CLI (`D161`)

On the fixed gate: 8 of 9 at `mutation_score` 1.0. The one failure was
the spec contradicting itself — the snapshot must be embedded in a
`<script type="application/json">` block, its not-ready reasons say
"run hotdocs generate", and `AC-UI-003` banned that text from any
script element. Scoped to executable script, the next round passed 9
of 9 at 0.75, nine of fourteen survivors in `main`. Covering every CLI
flag form landed it at 0.95.
