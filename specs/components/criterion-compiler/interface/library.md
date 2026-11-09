# Library

```
compile(component_id: str, repo_root: Path, target: str = "pytest", out_dir: Path | None = None) -> CompileReport

compile_criterion(criterion: ParsedCriterion, surface: InterfaceSurface | None = None) -> dict

GATE_VERSION: str  # exactly "criterion-compiler@1.0.0"
```

`GATE_VERSION` is a module-level constant, also the `gate_version` in
every `CompileReport`. `provenance-checker` reads it into every
component's provenance key, so it changes only when compiled output
would change.

`compile` is a pure function over corpus state at `repo_root` — no network
access, no model calls, no side effects beyond writing the files it's
asked to write. `out_dir` (the CLI's `--out`) is where compiled test files are
written, default `verification/<slug>/compiled/`.

`compile_criterion` (`R-COMPILE-012`, `D59`) is the lower-level
primitive `compile` itself uses for each criterion it finds — exposed
publicly for a caller compiling criterion content that doesn't live
under any one component's `acceptance/` directory (e.g.
`capability-scenario-verifier`'s product-capability scenarios). No
directory scanning, no file I/O: given an already-parsed
`ParsedCriterion` (a dataclass in this module, fields `criterion_id`,
`covers`, `kind`, `gherkin`, `file`, built by keyword) and
an optional `InterfaceSurface` (omit it for content black-box against
more than one component, which has no single surface to resolve
against), returns `{"status": "compiled", "source": <text>}` or
`{"status": "error", "message": <text>}` — never raises, and never
writes anything to disk itself. With no surface, only steps naming no
function, endpoint or type compile (`a <fixture-name> is <literal>`,
`<result-path> equals <literal>`); any other is an error naming it.

`compile` reads a component's `InterfaceSurface` from its `interface/`:
each line of a plain fenced block in `library.md` that starts
`name(params)` (no `def`) declares function `name`, with the parameter
names before any `:` or `=`; each `interface/data/*.md` whose heading is
``# `Type` `` declares `Type`, its fields the keys of the file's first
`json` example.

`InterfaceSurface.module_name` (`R-COMPILE-013`, `D62`) is the target
component's real importable module name (its underscored slug). Any
emitted reference to a function or type resolved against the surface
is qualified with it (`<module_name>.<name>`), and the emitted file
gets exactly one top-level `import <module_name>` line if — and only
if — at least one step actually needed it. A caller that *executes*
emitted output (anything dispatching a `compiled`-kind criterion, see
`R-COMPILE-013`) must scope its import search path to
`gen/<component>/` itself, not a broader ancestor.

Implements: `specs/architecture/step-phrase-grammar.md`
