# R-IMPACT-007

**R-IMPACT-007** — If the corpus has not passed `spec-linter` cleanly (any
  `fail`-severity finding present, including an unresolved cycle or a
  dangling reference anywhere in the graph, not only in the changed specs),
  the analyzer MUST fail closed — report a precondition error and compute no
  blast radius — rather than attempt a best-effort traversal over a graph it
  cannot trust.
