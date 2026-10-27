# R-LINT-015

**R-LINT-015** — For a `Definitions`-section entry that names a glossary
  term but is *not* caught by R-LINT-011 (i.e. not a near-verbatim copy), the
  linter MUST run an `llm-judge` evaluation of whether the local text is
  consistent with (a permitted delta on) the glossary's definition, versus
  substantively conflicting with it (a true redefinition in different words).
  A conflict MUST be reported as a `fail`-severity finding with structured
  rationale (per `SPEC_GUIDELINES.md` §5). **When no model is configured at
  all, this one requirement MUST be skipped with a visible, non-silent
  notice** — not treated as passing, not a crash.
