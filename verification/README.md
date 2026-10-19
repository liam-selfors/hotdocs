# Verification

Generated tests (`compiled`, `generated-test`, and `llm-judge` outputs),
contract/drift checks, and `corpus-graph.json` — the single generated
manifest the D8 traceability matrix and the D9 graph/docs explorer both
render from.

See `SPEC_GUIDELINES.md` §6 (verification gates) and §7 (provenance).

## `spec-linter/`

29 tests, covering all 22 `AC-LINT-*` criteria plus a sanity smoke test and
an interface-surface-counting regression suite. **Hand-authored bootstrap**
— `criterion-compiler` doesn't exist yet to have compiled these from
`acceptance/`'s Gherkin blocks the normal way. Run with `pytest` (not
vendored into the repo — install into your own environment). See
`BOOTSTRAP.md` in this directory for the full account, including a real bug
the bootstrap caught that hand-built fixtures alone had missed, and a note
on the D15 one-file-per-unit layout this suite was later rewritten for.

Everything else fills in as the corresponding components get specced and
(eventually) really generated.
