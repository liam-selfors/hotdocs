# Library

```
compile(component_id: str, repo_root: Path, target: str = "pytest") -> CompileReport

compile_criterion(criterion: ParsedCriterion, surface: InterfaceSurface | None = None) -> dict
```

`compile` is a pure function over corpus state at `repo_root` — no network
access, no model calls, no side effects beyond writing the files it's
asked to write. (Previously `compile(acceptance_md: Path, interface_md:
Path, target: str = "pytest")`, taking two explicit file paths; updated
for `D1`'s one-file-per-unit layout, where a component's `acceptance/`
and `interface/` are directories at known paths given its id, not
individual files to pass in by hand.)

`compile_criterion` (`R-COMPILE-012`, `D59`) is the lower-level
primitive `compile` itself uses for each criterion it finds — exposed
publicly for a caller compiling criterion content that doesn't live
under any one component's `acceptance/` directory (e.g.
`capability-scenario-verifier`'s product-capability scenarios). No
directory scanning, no file I/O: given an already-parsed
`ParsedCriterion` (`{criterion_id, covers, kind, gherkin, file}`) and
an optional `InterfaceSurface` (omit it for content black-box against
more than one component, which has no single surface to resolve
against), returns `{"status": "compiled", "source": <text>}` or
`{"status": "error", "message": <text>}` — never raises, and never
writes anything to disk itself.

`InterfaceSurface.module_name` (`R-COMPILE-013`, `D62`) is the target
component's real importable module name (its underscored slug). Any
emitted reference to a function or type resolved against the surface
is qualified with it (`<module_name>.<name>`), and the emitted file
gets exactly one top-level `import <module_name>` line if — and only
if — at least one step actually needed it. A caller that *executes*
emitted output (anything dispatching a `compiled`-kind criterion, see
`R-COMPILE-013`) must scope its import search path to
`gen/<component>/` itself, not a broader ancestor.
