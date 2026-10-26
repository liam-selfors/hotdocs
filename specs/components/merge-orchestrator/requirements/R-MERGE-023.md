# R-MERGE-023

**R-MERGE-023** — Within one blast radius, generation calls
  (`R-MERGE-005`) MUST be sequenced in `depends_on` order: a
  component's `generator` call MUST NOT start before every dependency
  in this radius has finished its own (`R-ASSEMBLE-011`'s
  `dependency_usage` needs each one's code current). Components with
  no `depends_on` relationship MAY still run in parallel
  (`R-MERGE-008`).
