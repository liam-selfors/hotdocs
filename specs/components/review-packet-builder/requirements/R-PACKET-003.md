# R-PACKET-003

**R-PACKET-003** — The packet MUST list which components were
  regenerated — exactly the keys of `provenance-tracker`'s own
  `VerifyReport.components` (`D90`), never a live `impact-analyzer`
  call of this component's own: `check_readiness` already resolved
  the blast radius internally before returning.
