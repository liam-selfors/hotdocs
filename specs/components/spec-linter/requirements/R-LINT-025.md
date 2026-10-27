# R-LINT-025

**R-LINT-025** — A component's `Purpose` section MUST stay within a
  per-section word cap (warn above 80, fail above 150) — `SPEC_
  GUIDELINES.md` §3.4's "one paragraph" rule, checked mechanically
  rather than left as an unenforced description. Now that `D21`/
  `R-LINT-024` give `Purpose` nowhere to hide decision-citation-laden
  rationale, a `Purpose` section that's still long is several
  paragraphs' worth of dependent-safe description disguised as one —
  genuinely worth a human's attention, the same signal `R-LINT-023`
  already gives for an oversized `requirements/`/`acceptance/` file.
