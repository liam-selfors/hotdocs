# R-PROBE-004

**R-PROBE-004** — `probe` MUST compare each fake's parameter count with
  the interface it stands in for, best-effort. Parse every
  `name(params) -> ReturnType` signature in each `dependency_interfaces`
  value; a comma inside brackets never splits a parameter
  (`dict[str, str]` is one), and `*` alone, `self` and `/` are not
  parameters. A `def` is a fake, and checked, only when it stands in for
  a dependency function: one inside a string literal of the test that
  parses as Python, a fake module's source; or a top-level `def`, or a
  simple `name = other_name` alias of one, installed under a dependency
  function's name by `monkeypatch.setattr(target, "<name>", fn)`,
  `setattr(target, "<name>", fn)` or `target.<name> = fn`, checked as
  `<name>`. A top-level helper installed nowhere is never a fake,
  whatever its name (`D334`). For each fake, compare parameter counts; a
  `*args` or `**kwargs` parameter on the fake satisfies any count, and a
  name several dependencies define matches if it fits any of them. A
  mismatch is one `fake_signature_mismatch` finding with the `def`'s line
  and the message
  `<name> takes <n> parameters; the interface of <component_id> gives <m>`.
  A signature that does not parse unambiguously is skipped.
