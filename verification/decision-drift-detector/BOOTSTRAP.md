# Bootstrap Account: `decision-drift-detector`

Cold-generated, not hand-written — a real model call, through a real
`generator` dispatching through a real `llm-endpoint`, from this
component's own assembled spec bundle and nothing else, with real
`test-author`-authored criterion tests and real `verifier-orchestrator`
mutation scoring. Landed at 5 of 5 criteria passing,
`mutation_score=0.84`, after eleven real rounds spanning five
decisions (`D133`–`D137`) — most of them diagnosing a single root
cause per round, never patched by hand.

## Round 1 (`D133`): wrong `kind:` entirely

First real attempt: all three criteria failed identically with
`step '...' does not match any recognized template in the step
grammar` — not a candidate issue at all. Diagnosed against
`pipeline/criterion-compiler/criterion_compiler.py`'s own fixed
grammar (`R-COMPILE-001`): a `Given`/`When`/`Then` step must match one
of a handful of rigid templates (a literal-value fixture, a single
function call, a single equality assertion) — nothing in that grammar
can express "build a git repo, make several commits, mark a decision
deprecated partway through." `find_decision_drift`/
`find_decision_impact` both read real git history directly; there is
no way to drive them with literal-value fixtures alone. All three
criteria were mis-declared `kind: compiled`; `component.md`'s own
prose even already described exactly the kind of real-git-repo setup
only `kind: generated-test` can express, self-contradicting its own
`kind:` claim. Changed to `generated-test`.

Also fixed in this round: the sandboxed bootstrap driver itself didn't
include `spec-bundle-assembler` among the infrastructure every sandbox
copies regardless of the target's own `depends_on` — needed by
`verifier_orchestrator.verify()` internally whenever any criterion is
`kind: generated-test`, found only once a target with zero spec-level
dependency on it first had one.

## Round 2 (`D134`): citation regex and dependency resolution

Second attempt: `mutation_score=1.0`, all four criteria still failed,
for two distinct causes. `AC-DRIFT-001`'s test cited `D17` in bare
prose; the candidate's citation regex required backtick-wrapping,
missing it — `R-DRIFT-001` had only said "the same citation shape
`R-LINT-026` already validates" in the abstract (that real rule is
`\bD\d+\b`, backtick-agnostic), implemented too narrowly on the first
try. `AC-DRIFT-002`/`AC-DRIFT-003` both failed because the fake
`graph-query-engine` the test wrote under its own `repo_root` was
never actually loaded: `_load_graph_query_engine()` derived the
dependency's path from `Path(__file__).resolve().parents[2]` — this
component's own on-disk location — never from the `repo_root`
parameter actually passed in. Inside this driver's own sandboxed
verification, that path happens to also contain a real copy of
`graph-query-engine`, so the candidate silently loaded the real module
instead of the fake and never called it — the identical bug class
`R-TRACK-011`/`R-VERIFY-013` already closed twice this session.
`R-DRIFT-001` amended with the literal regex; new `R-DRIFT-004` states
repo-root-relative resolution with a literal worked snippet.

## Round 3 (`D135`): a real DuckDB extension-registry conflict

Third attempt: all four criteria failed identically with
`InvalidInputException: ... already installed but the origin is
different` — a genuine machine-level DuckDB extension conflict, not a
logic bug. Diagnosed directly: every existing caller of
`graph-query-engine`'s `load_views` already installs the extension as
`INSTALL yaml FROM community`; this candidate wrote a bare `INSTALL
yaml`, which defaults to a different registry and conflicts outright
once the community-origin extension is already cached. Root cause:
`graph-query-engine`'s own `interface/library.md` only said "the
`yaml` community extension" in prose, never the literal incantation —
fixed there (`D135`), not in this component's own spec, since every
future caller needs the same fix.

## Round 4 (`D136`): the CLI entry point had zero coverage

Fourth attempt: all four criteria passed behaviorally.
`mutation_score=0.6`. Same shape as `provenance-writer`'s own `D130`:
every criterion exercises `find_decision_drift`/`find_decision_impact`
directly as a library call, none through `main()` — `interface/cli.md`
documents a real two-subcommand CLI no requirement or acceptance
criterion had ever covered. New `R-DRIFT-005`/`AC-DRIFT-005` close it.

## Round 5 (`D137`): scenario gaps, not spec gaps

Rounds 5 through 9 all passed behaviorally once `D134`'s fixes landed,
but `mutation_score` oscillated `0.58`–`1.0` across different
test-authoring seeds against the identical spec and candidate.
Diagnosed by running the real mutation harness directly against a
representative round: nine consistently surviving mutants clustered in
three functions no scenario precisely exercised — `_latest_by_
ratification` (the tie-break among *multiple* decisions superseding
the same cited one), `_discover_repo_root` (the no-`--repo-root`
default path), `_parse_args` (an invalid `--format` value). Added the
missing scenarios directly to `AC-DRIFT-001`/`AC-DRIFT-005` rather
than new requirements, since the behavior was already specified —
only the Gherkin's own coverage was thin.

Rounds 10–11 (seeds 3 and 5) surfaced one more thing worth noting but
not fixing further: round 10's own test-authoring wrote an
unusually sophisticated fake `graph-query-engine` that derives
`decision_lineage` dynamically from real git history inside the test
itself (via `git log --follow --diff-filter=A`) rather than hardcoded
literal commits — a more realistic fixture than any earlier round, but
one round's own instance of it had an internal bug unrelated to the
real candidate (confirmed: the same candidate code scored
`mutation_score=1.0` in that exact round). Round 11 (seed 5) landed
clean: all 5 criteria pass, `mutation_score=0.84`. Swapped in.
`model_pin` set to `claude-sonnet-5`.

Blast radius checked (`D99`): no already-built component depends on
`comp-decision-drift-detector` yet.
