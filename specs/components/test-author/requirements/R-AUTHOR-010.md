# R-AUTHOR-010

**R-AUTHOR-010** — The prompt MUST always include (a fixed,
  cross-cutting instruction, never bundle-derived content — the same
  category `generator`'s own `R-GEN-015` output-layout rule already
  established) a statement of this corpus's dependency-resolution
  convention: no component in this corpus is statically importable by
  another; a component's own code resolves each dependency dynamically,
  at runtime, from `<repo_root>/gen/<dependency-slug>/<module_name>.py`
  (a flat module) or `<dependency-slug>/__init__.py` (a package) —
  never a name Python's own import system would find on `sys.path`
  without that explicit file-path resolution, and never a name
  `sys.modules` injection or `unittest.mock.patch("<name>...")` can
  intercept by itself. A test needing to fake a dependency's behavior
  MUST instead write a fake module file at that exact real path, under
  a fresh temporary `repo_root`, and pass that `repo_root` through to
  the function under test, letting the component's own loader find it
  naturally.

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
