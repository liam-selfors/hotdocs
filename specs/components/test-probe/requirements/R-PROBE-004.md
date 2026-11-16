# R-PROBE-004

**R-PROBE-004** — `probe` MUST compare each fake's parameter count with
  the interface it stands in for, best-effort. Parse every
  `name(params) -> ReturnType` signature in each `dependency_interfaces`
  value; a comma inside brackets never splits a parameter
  (`dict[str, str]` is one), and `*` alone, `self` and `/` are not
  parameters. Walk the test's top-level `def`s, simple `name = other_name`
  aliases resolved to their target's parameter count, and string
  literals that parse as Python, collecting the `def`s inside them. For
  a name matching a dependency function, compare parameter counts; a
  `*args` or `**kwargs` parameter on the fake satisfies any count, and a
  name several dependencies define matches if it fits any of them. A
  mismatch is one `fake_signature_mismatch` finding with the `def`'s line
  and the message
  `<name> takes <n> parameters; the interface of <component_id> gives <m>`.
  A signature that does not parse unambiguously is skipped.
