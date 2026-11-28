# R-COMPILE-013

**R-COMPILE-013** — Emitted test code that references the target
  component's own functions or types (any `When ... is invoked` or
  `Given a <Type> with ...` step bound against a resolved
  `InterfaceSurface`) MUST import the target module by its
  `InterfaceSurface.module_name` and qualify every such reference with
  it (`<module_name>.<name>`) — never a bare, unqualified name relying
  on a caller to have pre-populated globals (`D62`).
