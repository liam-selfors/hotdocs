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
  coarse default every other `interface/` file kind already has (`D2`).

  **`depends_on_guarantees`'s real frontmatter shape** (`D49`, found
  missing from this bundle's own visible text, though already
  documented for humans in `SPEC_GUIDELINES.md` §2, which no
  `SpecBundle` ever includes): a flat list of bare `G-<comp>-NNN` id
  strings — e.g. `depends_on_guarantees: [G-CACHE-001]` — never a
  nested structure naming the owning component per entry. A `G-id`'s
  owning component is **never** parsed out of the id string itself
  (ambiguous once a component's own slug contains hyphens); it MUST be
  determined by which component's real `interface/guarantees/`
  directory actually contains a file with that id.

  This narrowing is **strictly opt-in**: a dependent's own silence (no
  `depends_on_guarantees` declared) MUST NEVER be read as "this dependent
  relies on nothing here" — only an explicit, non-empty declaration
  narrows anything. Getting a declared list wrong (under-claiming) is a
  real residual risk this requirement does not eliminate — it is
  structurally impossible for a graph-reachability computation to verify
  a claim about what code *actually* relies on — which is exactly why
  `D2`'s capability-scenario gate (`capability-scenario-verifier`, its
  own provenance checked by `provenance-tracker`'s `hotdocs verify`,
  `D89`) exists as a permanent backstop, not a transitional one,
  independent of how precise these declarations get.
