# R-GEN-015

**R-GEN-015** — The model call MUST instruct the candidate to lay out
  its own output as either a flat `<slug_with_underscores>.py` module
  or a `<slug_with_underscores>/` package (with `__init__.py`) directly
  under `gen/<component>/` — never a deeper layout (e.g. a `src/`
  subdirectory) and never a separately-installed distribution, since
  `spec-bundle-assembler`'s `dependency_usage` (`R-ASSEMBLE-011`) only
  looks in those two shapes (`D46`). This is fixed scaffolding the
  prompt always includes, like the nonce-delimiter format (`D38`), not
  bundle content.

  Before writing, generator MUST also strip one redundant leading
  `gen/<component>/` or `<component>/` from any returned file path —
  the model restating the directory it is already writing into — so
  `<component>/<slug_with_underscores>.py` is written as
  `<slug_with_underscores>.py`. No other path is rewritten (`D165`).
