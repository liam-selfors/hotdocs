# R-GEN-015

**R-GEN-015** — The model call MUST instruct the candidate to lay out
  its own output as either a flat `<slug_with_underscores>.py` module
  or a `<slug_with_underscores>/` package (with `__init__.py`) directly
  under `gen/<component>/` — never a deeper layout (e.g. a `src/`
  subdirectory) and never a separately-installed distribution. This is
  not a style preference: `spec-bundle-assembler`'s `dependency_usage`
  (`R-ASSEMBLE-011`) only ever looks for a dependency's code in those
  two exact shapes, and silently (by design, fail-to-empty) returns
  nothing for one it can't find there — found only once a real
  candidate chose a `src/` layout instead and would have silently
  broken `dependency_usage` for every future dependent (`D46`). This
  is a cross-cutting output-format instruction the prompt always
  includes, the same way the nonce-delimiter format is (`D38`) — never
  bundle content, and so not subject to `R-GEN-001`'s "constructed from
  exactly the bundle's fields" boundary, which governs *content*
  sections, not generator's own fixed scaffolding around them.
