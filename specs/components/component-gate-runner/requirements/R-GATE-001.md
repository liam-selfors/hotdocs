# R-GATE-001

**R-GATE-001** — For a non-sealed component, MUST first obtain the
  current provenance key from `provenance-checker`'s
  `current_provenance_key` and pass it to `check_provenance`
  (`D29`/`D163`) — never computing a hash or gate-version map itself.
  A hit whose `verification_report.overall` is `"pass"` and whose
  `license_scan.blocked` is not `true` MUST short-circuit: the result
  copies the hit's three reports, and nothing else in
  `interface/library.md`'s list is called — no generation,
  verification, scan, or write. Any other result, including a hit
  recording a failed attempt, proceeds as a miss (re-verified
  first when `R-GATE-011` applies). A sealed component is never
  checked (`R-GATE-007`).
