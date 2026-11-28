# R-DOCS-008

**R-DOCS-008** — The DAG view MUST be laid out by the asset's pure
  `layoutGraph(nodes, edges)` exactly as `interface/assets/app.js.md`
  defines it: one column per node type (capability, component, var,
  anything else, left to right), nodes stacked in page order within a
  column, edges drawn as straight lines between node centres, each
  carrying its kind's edge class (`specs/architecture/visual-style.md`
  "Edges"), which colours it, an edge to or from a node not in the graph not drawn, and the
  drawing's height fitted to its tallest column. The layout is a pure
  function of the node and edge lists, so the same graph always draws
  the same way, and criteria pin its exact coordinates through
  `asset_runner` (`D343`).

  A column layout by type, not a layered layout by dependency depth:
  it is the layout the page has always drawn, now stated exactly.
