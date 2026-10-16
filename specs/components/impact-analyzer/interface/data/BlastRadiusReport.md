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

`reason` is always one of `direct` | `transitive-interface` |
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
