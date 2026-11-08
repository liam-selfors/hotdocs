# R-AUTHOR-010

**R-AUTHOR-010** — The prompt MUST always state this corpus's
  dependency-resolution convention: how the component under test
  resolves its OWN dependencies. It MUST also say, in those words, that
  the component under test itself needs no custom loader: a plain
  `import <module_name>` (`D97`).

  MUST state: no dependency is statically importable; resolution is
  dynamic, at runtime, from
  `<repo_root>/gen/<dependency-slug>/<module_name>.py` (flat) or
  `.../<module_name>/__init__.py` (package), else the tool's own copy
  (`D199`), so omitting one never makes it missing — never interceptable by
  name-based `sys.modules` injection or `mock.patch`. To fake a
  dependency, write a fake module file under a fresh temporary
  `repo_root` — **always flat-module shape** (`D97`): every real
  loader checks flat first. `module_name` is the slug with hyphens
  replaced by underscores, never `"__init__"`.

  MUST include a literal snippet registering the module in
  `sys.modules` **before** `exec_module`, which a dataclass needs (`D96`).
