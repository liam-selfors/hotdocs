# Verification

Generated tests (`compiled`, `generated-test`, and `llm-judge` outputs),
contract/drift checks, and `corpus-graph.json` — the single generated
manifest the D8 traceability matrix and the D9 graph/docs explorer both
render from.

See `SPEC_GUIDELINES.md` §6 (verification gates) and §8 (provenance).

## `spec-linter/`

14 tests, one per `AC-LINT-*` criterion, plus one sanity smoke test. **Hand-
authored bootstrap** — `criterion-compiler` doesn't exist yet to have
compiled these from `acceptance.md`'s Gherkin blocks the normal way. Run
with `pytest` (not vendored into the repo — install into your own
environment). See `BOOTSTRAP.md` in this directory for the full account,
including a real bug the bootstrap caught that hand-built fixtures alone had
missed.

Everything else fills in as the corresponding components get specced and
(eventually) really generated.
