# R-GEN-015

**R-GEN-015** — The model call MUST instruct the candidate to lay out
  its own output as either a flat `<slug_with_underscores>.py` module
  or a `<slug_with_underscores>/` package (with `__init__.py`) directly
  under `gen/<component>/` — never a deeper layout (e.g. a `src/`
  subdirectory) and never a separately-installed distribution (`D46`).
  It names the real module, e.g. `widget_maker.py` or `widget_maker/`
  for `comp-widget-maker`, then each declared asset path
  (`interface/library.md`'s Assets) as a file the reply must also
  write, and says no other non-`.py` file may be written (`D343`, `D38`).

  Before writing, generator MUST also strip one redundant leading
  `gen/<component>/` or `<component>/` from any returned file path, so
  `<component>/<slug_with_underscores>.py` is written as
  `<slug_with_underscores>.py`. No other path is rewritten (`D165`).
