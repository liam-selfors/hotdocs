# Asset `static/app.js`

Kind `javascript` (`specs/architecture/asset-kind-javascript.md`, `D343`): the
page's only script, at `gen/provenance-tracker-ui/static/app.js`, next
to the flat module `provenance_tracker_ui.py`.

```
export function hiddenByStatus(nodes, filter)
export function init(document)
```

## `hiddenByStatus(nodes, filter)`

- `nodes`: a list of `{"id": str, "status": str}`, ids distinct.
- `filter`: a string, one of the filter buttons' `data-filter` values
  (`R-UI-010`), though any string is accepted.
- Returns an object mapping every node's `id` to a boolean, `true` when
  that node is hidden under `filter`:
  - `filter` `"all"`: every node `false`.
  - any other `filter`: `false` exactly when the node's `status` equals
    `filter` (exact, case-sensitive string equality), otherwise `true`.
    A `filter` matching no status, such as `"bogus"`, hides every node.
- An empty `nodes` returns `{}`. Never throws for well-formed input;
  never reads or changes anything but its arguments.

## `init(document)`

Browser-only, never called by tests. For each `button[data-filter]`,
on `click`: builds `nodes` from every `li.node` element
(`{"id": data-node-id, "status": data-status}`), calls
`hiddenByStatus(nodes, <the button's data-filter>)`, and sets each
`li.node` element's `hidden` property to that node's result. It makes
no decision of its own (`specs/architecture/asset-kind-javascript.md`'s generator
guidance).
