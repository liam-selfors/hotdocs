# R-IMPACT-008

**R-IMPACT-008** — For a changed component whose `interface/guarantees/`
  content changed relative to the prior commit (compared per-file,
  independently), the analyzer MUST include every component with a
  `depends_on` edge to it — **narrowed** as follows: if the dependent
  declares one or more `depends_on_guarantees` entries whose owning
  component is this upstream component, the dependent MUST be included
  only if at least one of those *specifically declared* `G-id` files is
  among the changed guarantee files, tagged `transitive-guarantee` and
  naming the specific `G-id`(s) that changed. If the dependent declares no
  `depends_on_guarantees` entries for this upstream component at all, it
  MUST be included unconditionally whenever *any* file under that
  component's `interface/guarantees/` changed, tagged
  `transitive-guarantee` naming the upstream component — the same safe,
  coarse default every other `interface/` file kind already has (D16).

  This narrowing is **strictly opt-in**: a dependent's own silence (no
  `depends_on_guarantees` declared) MUST NEVER be read as "this dependent
  relies on nothing here" — only an explicit, non-empty declaration
  narrows anything. Getting a declared list wrong (under-claiming) is a
  real residual risk this requirement does not eliminate — it is
  structurally impossible for a graph-reachability computation to verify
  a claim about what code *actually* relies on — which is exactly why
  D16's capability-scenario gate (`capability-scenario-verifier`, called by
  `merge-orchestrator` per R-MERGE-014) exists as a permanent backstop,
  not a transitional one, independent of how precise these declarations
  get.
