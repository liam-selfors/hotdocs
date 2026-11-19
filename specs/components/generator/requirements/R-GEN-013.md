# R-GEN-013

**R-GEN-013** — When the bundle's `dependency_usage` field
  (`R-ASSEMBLE-011`, `D37`) is non-empty for a dependency, the model
  call MUST include it as its own clearly distinguished section,
  never merged with `dependency_interfaces`. Empty for a dependency with no real
  code yet; this component MUST NOT treat that absence as an error or
  a reason to refuse.
