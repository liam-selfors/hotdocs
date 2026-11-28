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
  `transitive-guarantee` naming the upstream component (`D2`).

  A guarantee file is a `G-*.md` file directly in `interface/guarantees/`;
  its `G-id` is the file's stem. A guarantee file added or removed counts
  as changed. No other file there (a `README.md`, a non-`.md` file, a file
  in a subdirectory) is a guarantee file, and a change to one triggers
  nothing under this requirement. `guarantee_ids` lists the qualifying
  `G-id`s sorted.

  **`depends_on_guarantees`'s frontmatter shape** (`D49`): a flat list of bare `G-<comp>-NNN` id
  strings — e.g. `depends_on_guarantees: [G-CACHE-001]` — never a
  nested structure naming the owning component per entry. A `G-id`'s
  owning component is **never** parsed out of the id string itself
  (ambiguous once a component's own slug contains hyphens); it MUST be
  determined by which component's real `interface/guarantees/`
  directory actually contains a file with that id.

  This narrowing is **strictly opt-in**: a dependent's own silence (no
  `depends_on_guarantees` declared) MUST NEVER be read as "this dependent
  relies on nothing here" — only an explicit, non-empty declaration
  narrows anything.
