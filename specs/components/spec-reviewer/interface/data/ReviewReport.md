# `ReviewReport`

```json
{
  "targets": ["comp-foo"],
  "criteria_checked": ["AC-FOO-001", "AC-FOO-002"],
  "findings": [
    {"criterion_id": "AC-FOO-002", "kind": "invisible_reference",
     "token": "--fast", "message": "`--fast` appears in AC-FOO-002 but not in what its test author sees"}
  ],
  "gaps": [
    {"criterion_id": "AC-FOO-001", "kind": "unstated_behavior",
     "missing": "what foo returns for a negative x",
     "proposed_text": "`foo(x)` MUST raise `ValueError` for a negative `x`.",
     "target_file": "specs/components/foo/requirements/R-FOO-001.md"}
  ],
  "writable": {"AC-FOO-001": false, "AC-FOO-002": true},
  "lint_findings": [],
  "proposals": [],
  "degraded": false
}
```

A dataclass with these fields in this order that also reads as a mapping
(`report["gaps"]`), with a `to_dict()` giving the JSON form.

- `findings` holds the deterministic checks' results; `kind` is
  `asset_interface_missing`, `invisible_reference` or
  `model_unparseable`. An `asset_interface_missing` finding belongs to
  no criterion: its `criterion_id` is the component's id (`comp-foo`)
  and its `token` the asset's path, such as `static/app.js`
  (`R-REVIEW-008`).
- `gaps` holds the model's; `kind` is `guess` or `unstated_behavior`.
- `writable` maps each checked criterion to the model's verdict, or
  `null` without a model or for an unparseable reply.
- `lint_findings` holds `spec-linter`'s findings for the named components,
  each as its `Finding`'s fields in a dict.
- `proposals` lists the files written under `.hotdocs/proposals/`,
  relative to `repo_root`.
