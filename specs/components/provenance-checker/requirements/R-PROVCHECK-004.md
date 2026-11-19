# R-PROVCHECK-004

**R-PROVCHECK-004** — MUST be read-only: MUST NOT write, modify, or
  delete `.provenance.json` or any other file; an adapter's
  `provision` (`R-PROVCHECK-009`) is the only code it calls that may
  write, under `.hotdocs/env/`.
