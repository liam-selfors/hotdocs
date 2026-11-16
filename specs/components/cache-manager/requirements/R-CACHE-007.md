# R-CACHE-007

**R-CACHE-007** — `put` MUST reject (not silently accept) a result payload
  whose shape doesn't match the schema expected for the `gate_version`'s
  declared gate type — guards against cache poisoning from a caller bug
  writing, e.g., a `LintReport`-shaped payload under a `license_scanner`
  `gate_version`.

  Each gate type's exact required payload keys are documented once, in
  `interface/data/CachedResult.md` (`D40`) — not repeated here, since a
  dependent only ever sees a dependency's `interface/` content, never
  its `requirements/` (`R-ASSEMBLE-002`); a copy living only in this
  file would be real and correct but invisible to anything cold-
  assembling a bundle against this contract.
