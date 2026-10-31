# `TrackerSnapshot`

```json
{
  "scope": "blast-radius",
  "changed_ids": ["comp-foo"],
  "ready": false,
  "not_ready_reasons": ["comp-bar: no provenance for current spec state — run hotdocs generate comp-bar"],
  "nodes": [
    { "id": "comp-foo", "kind": "component", "status": "passing", "attempts": [], "retry_feedback": [] },
    { "id": "comp-bar", "kind": "component", "status": "missing",
      "attempts": [ { "attempt_id": "2026-10-25T14:32:01Z-a1b2c3", "...": "an AttemptRecord" } ],
      "retry_feedback": ["R-BAR-002"] },
    { "id": "comp-baz", "kind": "component", "status": "not-attempted", "attempts": [], "retry_feedback": [] },
    { "id": "P-ZERO-EDIT", "kind": "capability", "status": "failing", "attempts": [], "retry_feedback": [] }
  ],
  "edges": [ { "from": "comp-foo", "to": "P-ZERO-EDIT", "kind": "realizes" } ]
}
```

`scope`, `ready`, and `not_ready_reasons` are copied verbatim from the
`VerifyReport`; `changed_ids` is the argument passed (`null` for the
whole-corpus view). `nodes` holds exactly the keys of
`VerifyReport.components` and `VerifyReport.capabilities`, sorted by
`id`. `edges` holds every `corpus-graph.json` edge whose `from` and `to`
are both in `nodes`.

`status` is one of exactly four strings, each a direct mapping of
report fields (`R-UI-002`/`R-UI-005`), never a recomputation:

- component, `hit` true, `verification_report.overall` `"pass"`, not
  `license_scan.blocked`, not `secret_scan.flagged` → `"passing"`
- component, `hit` true, anything else → `"failing"`
- component, `hit` false, at least one `AttemptRecord` → `"missing"`
- component, `hit` false, no `AttemptRecord` → `"not-attempted"`
- capability, `capability_scenario_report[<id>].overall` `"pass"` →
  `"passing"`, otherwise `"failing"`

`attempts` is every `AttemptRecord` for that component, oldest first;
`retry_feedback` is `last_requirement_failures`' result. Both are `[]`
for a capability and for a `"passing"` component.
