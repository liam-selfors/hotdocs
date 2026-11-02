# R-AUTHOR-010

**R-AUTHOR-010** — The prompt MUST always state this corpus's
  dependency-resolution convention — how the component under test
  resolves its OWN dependencies internally, never how the test
  imports the component under test itself (always a plain
  `import <module_name>`, no custom loader, `D97`).

  MUST state: no dependency is statically importable; resolution is
  dynamic, at runtime, from
  `<repo_root>/gen/<dependency-slug>/<module_name>.py` (flat) or
  `.../<module_name>/__init__.py` (package) — never interceptable by
  name-based `sys.modules` injection or `mock.patch`. To fake a
  dependency, write a fake module file under a fresh temporary
  `repo_root` — **always flat-module shape** (`D97`): every real
  loader checks flat first. `module_name` is the slug with hyphens
  replaced by underscores, never `"__init__"`.

  MUST include the one correctness-critical step as a literal worked
  snippet: register the module in `sys.modules` **before**
  `exec_module` — a dataclass's class body resolves
  `sys.modules[__module__]` while executing.

  (`D96`/`D97`)
