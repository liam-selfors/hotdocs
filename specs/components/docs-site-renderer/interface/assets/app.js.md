# Asset `static/app.js`

Kind `javascript` (`specs/asset-kinds/javascript.md`, `D343`): the DAG
view's only script, at `gen/docs-site-renderer/static/app.js`, beside
the package directory `docs_site_renderer/`.

```
export function layoutGraph(nodes, edges)
export function filterGraph(nodes, edges, query)
export function init(document)
```

`nodes` is a list of `{"id": str, "type": str}` with distinct ids, in
page order; `edges` a list of `{"from": str, "to": str, "kind": str}`.
Neither function changes its arguments.

## `layoutGraph(nodes, edges)`

Returns `{"width", "height", "nodes", "edges"}`:

- Column by `type`: `"capability"` 0, `"component"` 1, `"var"` 2, any
  other type 3. A node's row is the number of nodes before it in
  `nodes` with the same column.
- `"nodes"`: one `{"id", "x", "y", "labelX", "labelY"}` per node, in
  input order, with `x = 120 + 260 * column`, `y = 30 + 40 * row`,
  `labelX = x + 12`, `labelY = y + 4`.
- `"edges"`: for each edge whose `from` and `to` are both node ids, in
  input order, `{"index", "from", "to", "x1", "y1", "x2", "y2",
  "color"}`: `index` its position in `edges`, `(x1, y1)` the `from`
  node's `(x, y)`, `(x2, y2)` the `to` node's; `color` `"#1565c0"` for
  kind `"depends_on"`, `"#2e7d32"` for `"realizes"`, `"#ef6c00"` for
  any other kind. An edge with either end missing is left out.
- `"width"`: always `1100`. `"height"`: `60 + 40 * m`, `m` the largest
  number of nodes in one column, or `1` when `nodes` is empty.

## `filterGraph(nodes, edges, query)`

Returns `{"hiddenNodes", "hiddenEdges"}`:

- `"hiddenNodes"`: maps every node id to `false` when the id, lowercased,
  contains `query`, lowercased, as a substring, else `true`. The empty
  query is a substring of every id. Only the id is searched, never
  `type`; `query` is not trimmed.
- `"hiddenEdges"`: one boolean per edge, in input order: `false` when
  both `from` and `to` are node ids with `hiddenNodes` `false`, else
  `true` (an end that is not a node id counts as hidden).

## `init(document)`

Browser-only, never called by tests. Reads `nodes` from `#nodes .node`
(`data-id`, `data-type`) and `edges` from `#edges .edge` (`data-from`,
`data-to`, `data-kind`); draws `layoutGraph`'s result into `svg#dag`
(sets its `width`/`height`, one `line` per laid-out edge with `stroke`
its color, one clickable `g` per node with a circle at `(x, y)`, radius
8, and its id as text at `(labelX, labelY)`, linking to the node's
detail page). On `input` in `#search`, calls `filterGraph` with the
field's value and toggles class `hidden` on each list item and drawn
mark from the result. It decides nothing itself.
