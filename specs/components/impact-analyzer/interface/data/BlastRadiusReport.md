# `BlastRadiusReport`

```json
{
  "impacted": [
    {
      "component_id": "comp-foo",
      "reason": "direct",
      "via": null
    },
    {
      "component_id": "comp-bar",
      "reason": "transitive-interface",
      "via": "comp-foo"
    },
    {
      "component_id": "comp-baz",
      "reason": "transitive-var",
      "via": "VAR-CACHE-STORE-URL"
    },
    {
      "component_id": "comp-qux",
      "reason": "transitive-capability",
      "via": "P-ZERO-EDIT"
    },
    {
      "component_id": "comp-quux",
      "reason": "transitive-guarantee",
      "via": "comp-foo",
      "guarantee_ids": ["G-FOO-001"]
    }
  ],
  "precondition_error": null
}
```

`component_id` is always the full `comp-<slug>` form (`glossary.md`'s
"Component id / component slug" entry), matching exactly what a
caller's own `--changed` argument would use — never the bare slug,
even though some of this component's own internal data (e.g.
`spec-linter`'s `corpus.components` dict) is keyed by the bare form.

Each component appears at most once. One named in the changed ids is
always `direct`, whatever else would also include it. `impacted`
lists the `direct` entries first, then the rest, each part sorted by
`component_id`. When several transitive reasons would include one
component, the entry kept is the first found in this order: each
changed component in id order, its `transitive-interface` before its
`transitive-guarantee`; then each changed var in id order; then each
changed capability in id order. `reason` is always one of `direct` | `transitive-interface` |
`transitive-var` | `transitive-capability` | `transitive-guarantee`
(R-IMPACT-001/003/004/005/008). `via` names the specific upstream id that
triggered inclusion, `null` only for `direct`. `guarantee_ids` is present
only for `reason: transitive-guarantee` — the specific `G-id`(s) that
changed and triggered this inclusion (R-IMPACT-008); when the dependent
declared no `depends_on_guarantees` for this upstream component (the
coarse default), this lists every guarantee file that changed, not just
ones the dependent explicitly claimed to rely on. A non-null
`precondition_error` means `impacted` is empty and MUST be ignored by
callers (R-IMPACT-007) — it is not "nothing was impacted," it is "the
question could not be answered."
