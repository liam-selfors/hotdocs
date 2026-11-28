# R-PROVCHECK-013

**R-PROVCHECK-013** — A miss whose reason would be `gate_versions
  differ` MUST instead have `reason` `gates differ` (`D394`) when every
  manifest `gate_versions` entry that differs from the supplied one is
  an entry other than `generator`: a verifier, compiler, scanner or
  test-format version changed, not the code's producer, so the improved
  gates are run again on the committed code. A differing `generator`
  entry keeps `gate_versions differ`. A miss on the spec hash as well
  takes `R-PROVCHECK-011`'s or `R-PROVCHECK-012`'s reason, which comes
  first and allows the same gate differences.
