# R-AUTHOR-010

**R-AUTHOR-010** — The prompt MUST always include (a fixed,
  cross-cutting instruction, never bundle-derived content — the same
  category `generator`'s own `R-GEN-015` output-layout rule already
  established) a statement of this corpus's dependency-resolution
  convention, governing **how the component under test resolves its
  own dependencies internally** — never how the test itself imports
  the component under test, which is always a plain `import
  <module_name>` / `from <module_name> import ...`, since the test
  always runs with the component's own `gen/<component>/` directory on
  `PYTHONPATH` and Python's own import system already resolves that
  correctly whether the component is a flat module or a package. No
  custom loader is ever needed for the component under test itself
  (`D97`).

  The instruction MUST state: no dependency is statically importable;
  the component under test resolves each dependency dynamically, at
  runtime, from `<repo_root>/gen/<dependency-slug>/<module_name>.py`
  (flat) or `<dependency-slug>/__init__.py` (package) — never a name
  `sys.modules` injection or `unittest.mock.patch("<name>...")` can
  intercept by itself. If the test needs to fake a dependency's
  behavior, it MUST write a fake module file under a fresh temporary
  `repo_root` and pass that `repo_root` through to the function under
  test, letting the component's own loader find it naturally —
  **always as the flat-module shape** (`D97`): every real
  dependency-resolving component in this corpus checks the flat path
  first, so a fake written there is found regardless of which shape
  the real, unfaked dependency happens to use elsewhere, and this
  removes any ambiguity about imitating the package shape. `module_name`
  is the dependency's own slug with hyphens replaced by underscores —
  never a literal `"__init__"` or any other placeholder.

  The instruction MUST include the one correctness-critical step as a
  literal worked snippet, not prose alone: the freshly created module
  object MUST be registered in `sys.modules` **before**
  `exec_module` is called on it, since a dataclass's class body
  resolves its own module via `sys.modules[__module__]` while
  executing, and omitting this step produces a plausible-looking loader
  that still fails on any dependency whose own code defines a
  dataclass.

  **Found only once this corpus's convention had to survive contact
  with a genuinely independent author for the first time** (`D96`):
  three of five real `AC-TRACK-*` test authorings (bootstrapping
  `provenance-tracker`) failed for exactly this reason — one guessed a
  package-submodule import path that doesn't exist, two assumed
  dependencies were statically patchable by name, and the one that did
  correctly guess the real dynamic-loading shape for the component
  under test itself reproduced an *almost*-correct loader missing only
  the `sys.modules` pre-registration step, confirming prose alone
  (without the literal snippet) is not reliably sufficient.

  **Further narrowed after a retry** (`D97`): a reasonable reading of
  the first version of this instruction applied it to importing the
  component under test too, producing a custom loader for the
  component under test itself that got the package path wrong with no
  worked example to follow; a fake dependency written to imitate the
  package shape, also with no worked example, landed on a path no real
  loader in this corpus checks at all. Both closed by narrowing scope
  and the fake-is-always-flat rule above.
