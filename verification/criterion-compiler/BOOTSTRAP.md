# Bootstrap Account: `criterion-compiler`

Permanently hand-authored, not a temporary bootstrap exception like
`cache-manager`/`spec-bundle-assembler` were before `D50`/`D55`
onward, and not even structurally-permanent-but-eventually-self-hosted
like `llm-endpoint`/`generator`: `criterion-compiler` MUST never be
agent-generated, ever (`component.md`'s `sealed: true`, Purpose). The
trust anchor for `compiled`-kind criteria only holds if the compiler
that compiles them was never itself a candidate this methodology's own
verify-then-swap discipline had to approve.

**The real, corpus-wide gap found immediately before this component
was ever written (`D59`)**: every existing `kind: compiled` criterion
across every already-built component -- 200 of 200, checked
programmatically against the real grammar's six templates -- is
written in ordinary prose, not the step-phrase grammar this component
implements. None of them could have compiled. Reclassified to
`generated-test` first; see `D59` for the full account. This
component's own test suite (below) therefore uses a synthetic
`widget` fixture component, not any real corpus content -- exactly
what `constraints.md`'s "characterization coverage" clause already
anticipated ("the hand-authored reference fixture suite... living in
`verification/criterion-compiler/`", never "real corpus content").

**Design choices the spec left genuinely open, resolved here:**

- **Scenario grouping.** A `compiled` criterion's gherkin block may
  hold more than one scenario (`AC-COMPILE-011`/`012`'s own real text
  does this, even post-`D59`-reclassification, by structure). Resolved
  as: one or more `Given` lines, exactly one `When` line, one or more
  `Then` lines, each scenario separated by a blank line. More than one
  scenario in a file compiles to `test_<id>_scenario_<n>` functions;
  exactly one compiles to a bare `test_<id>`.
- **Implicit fixture name for `a <Type> with ...`.** The grammar names
  an explicit fixture for `a <fixture-name> is <literal>` but not for
  the `Type`-construction template. Resolved as the snake-cased `Type`
  name itself (`a Bundle with ...` binds `bundle`); a second
  construction of the same `Type` in one scenario gets a numeric
  suffix (`bundle_2`).
- **`<args>` syntax for `When` steps.** Not specified beyond "a call to
  the named function... capturing the result as `result`". Resolved
  as a single literal: an object literal becomes keyword arguments, an
  array literal becomes positional arguments, any other scalar/
  identifier becomes one positional argument.
- **Fixture substitution is real inlining, not a variable reference.**
  `AC-COMPILE-012` is explicit: "resolved to the literal... with no
  runtime lookup or evaluation in the generated code." A first draft
  emitted the bound *variable name* at each reference site (e.g.
  `process(user_id, {"owner": user_id})`) — compile-time *validated*,
  but not compile-time *inlined*, and caught by this component's own
  test for exactly that AC before being swapped in. Fixed: every
  reference resolves, recursively, to the fixture's own already-parsed
  literal value and is rendered as that value directly (`process("u1",
  {"owner": "u1"})`). The `Given` step's own setup line (`user_id =
  "u1"`) is still emitted regardless — that's `R-COMPILE-001`'s own
  unconditional "compiles to a bound local variable", not something
  substitution should remove.
- **`interface/` resolution.** `library.md`'s fenced code block is
  scanned for `name(params) -> ReturnType`-shaped lines to populate
  known function names and parameter names; `interface/data/<Type>.md`
  is scanned for its `# \`Type\`` heading and its JSON example's
  top-level keys as declared fields. Prose outside these two shapes is
  not parsed — `cli.md` is never consulted (no step template
  references CLI flags).
- **"the client calls `<METHOD>` `<path>` with `<args>`".** No
  component in this corpus implements an HTTP-serving endpoint yet, so
  this template has never been exercised against a real interface.
  Resolved as: the endpoint must be declared in `interface/` under the
  literal name `"<METHOD> <path>"` (e.g. `"GET /foo"`), and compiles to
  `result = client.<method>(<path>, <args>)` — a reasonable, documented
  interpretation, not yet validated against any real consumer.

Verified entirely without a model call (`R-COMPILE-008`'s own
requirement, structurally true here since nothing in this file ever
imports a model-calling dependency): all 12 tests pass, one per
`AC-COMPILE-*` criterion, against the synthetic `widget` fixture in
`conftest.py`.

**`D75`: `compile_criterion`, a directory-scanning-free primitive.**
Building `capability-scenario-verifier` (which needs to compile
`compiled`-kind criterion content that lives outside any component's
`acceptance/` directory — a product-capability scenario, black-box
against more than one component) found that `compile`'s own public
surface had no way to serve that need without a second, duplicated
compilation path, directly contradicting `R-SCENARIO-001`'s "no new
dispatch machinery" rule. Refactored `compile` to call a new, public
`compile_criterion(criterion, surface=None)` internally for each
criterion it finds — behavior-preserving (all 12 pre-existing tests
pass unchanged) — and exposed it for exactly this second caller.
`surface=None` is a real, valid input (not merely "no interface yet"):
a step that never references a function/type compiles fine with no
surface at all; one that does is still a located compile error, never
silently skipped for lack of one (`AC-COMPILE-013`).

**`D79`: emitted source never imported the target module.** Found
while building `verifier-orchestrator`, whose job is to *execute*
compiled scaffolding against real `gen/<component>/` code — something
no test here had ever done before (every prior test checked emitted
*content*, never ran the emitted function against a real target).
Running it surfaced that every `When ... is invoked` and typed
`Given` step compiled to a bare, unqualified call
(`do_the_thing(1)`), which only works by accident if a caller happens
to pre-populate globals. Fixed via `InterfaceSurface.module_name` (the
target component's underscored slug) and a `_qualify()` step that
prefixes every resolved function/type reference with it, emitting
exactly one top-level `import <module_name>` line if and only if some
step needed it (`R-COMPILE-013`, `AC-COMPILE-014`). This also exposed
a previously undocumented execution contract for any caller running
emitted output: the import search path must be scoped to the specific
`gen/<component>/` directory, not a broader ancestor like `gen/` —
otherwise `import <module_name>` resolves to an empty implicit
namespace package rather than the real module (no `__init__.py`
there). Now a formal part of `verifier-orchestrator`'s own
`R-VERIFY-001`.

All 15 tests pass, one per `AC-COMPILE-*` criterion (now 14 criteria,
`AC-COMPILE-014` covered by two tests), against the synthetic
`widget` fixture in `conftest.py` — still entirely without a model
call.
