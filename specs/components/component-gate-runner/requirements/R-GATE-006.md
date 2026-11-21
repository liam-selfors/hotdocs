# R-GATE-006

**R-GATE-006** — On a non-sealed miss whose generation produced files,
  MUST invoke `provenance-writer` once, after verification, both scans,
  and the attempt record (`R-GATE-008`) have concluded, passing
  `ProvenanceInputs` built exactly as `interface/library.md` states —
  `gate_versions` from the same provenance key `R-GATE-001` obtained,
  so what is written and what is later checked come from one
  definition (`D163`). When the loop's last generation result has no
  files, nothing new reached `gen/`, so no provenance is written.
