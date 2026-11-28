# R-DOCS-009

**R-DOCS-009** — Typing in the DAG view's search field MUST hide every
  node whose id does not contain the typed text, ignoring case, and
  every edge with an end hidden or missing, in both the drawing and the
  node and edge lists; clearing the field shows every node again. What
  is hidden is decided by the asset's pure `filterGraph(nodes, edges,
  query)` exactly as `interface/assets/app.js.md` defines it, and
  `init(document)` only applies its result (`D343`), which criteria
  check on the rendered page through the `browser` driver (`D373`).
