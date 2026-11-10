# R-CITE-003

**R-CITE-003** — Every `` the glossary's "<Term>" `` citation in a live
  document MUST resolve to a real bolded entry header in
  `specs/glossary.md` — same mechanism as `R-CITE-001` and `R-CITE-002`
  (`SPEC_GUIDELINES.md` §3.6) — matched case-exactly after collapsing
  whitespace, since prose hard-wraps. One trailing `,.;:` inside the
  closing quote is not part of the term, and a quoted text not starting
  alphanumerically, such as `"<Term>"` itself, is a placeholder, not a
  citation (`D176`).
