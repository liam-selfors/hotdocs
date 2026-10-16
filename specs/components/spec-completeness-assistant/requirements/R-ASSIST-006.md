# R-ASSIST-006

**R-ASSIST-006** — This component's output MUST NOT gate anything. It
  MUST NOT appear in `merge-orchestrator`'s `depends_on`, and its result
  MUST have no mechanism by which it can block a merge — advisory only, by
  construction, not by developer discipline.
