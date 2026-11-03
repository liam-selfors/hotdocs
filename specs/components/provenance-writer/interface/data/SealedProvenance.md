# `SealedProvenance` and `SealedProvenanceInputs`

The sealed provenance manifest, `<repo_root>/<source_path>/.sealed-provenance.json`
(`SPEC_GUIDELINES.md` §7). This document is its one definition: the
writer produces it, `provenance-checker` reads it, and both follow the
rules below exactly.

```json
{
  "kind": "sealed-provenance",
  "version": 1,
  "component_id": "comp-criterion-compiler",
  "owners": ["pipeline-team"],
  "source_path": "pipeline/criterion-compiler/",
  "source_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "verifier_version": "verifier-orchestrator@2.0.0",
  "characterization": { "overall": "pass", "criteria_passed": 15, "criteria_total": 15 },
  "written_at": "2026-11-02T00:00:00Z"
}
```

**Validity.** A document is a valid manifest only if all hold, and an
invalid one is never honored in any part:

- it is a JSON object with exactly the keys above, in no other shape;
  `characterization` has exactly its three keys;
- `kind` is `"sealed-provenance"`; `version` is the integer `1` (JSON
  `true` is not an integer, here or in any count below);
- `component_id` matches `^comp-[a-z0-9]+(-[a-z0-9]+)*$`;
- `owners` is a non-empty list of strings, each matching
  `^[a-z0-9]+(-[a-z0-9]+)*$`;
- `source_path` matches `^[A-Za-z0-9_][A-Za-z0-9_.-]*(/[A-Za-z0-9_][A-Za-z0-9_.-]*)*/?$`
  and its first segment is not `gen`;
- `source_hash` matches `^sha256:[0-9a-f]{64}$`;
- `verifier_version` matches `^verifier-orchestrator@[0-9]+\.[0-9]+\.[0-9]+$`;
- `characterization.overall` is `"pass"` or `"fail"`; `criteria_passed`
  and `criteria_total` are integers (never booleans) with
  `0 <= criteria_passed <= criteria_total`; `"pass"` additionally needs
  `criteria_total >= 1` and `criteria_passed == criteria_total`;
- `written_at` matches `^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$`.

No field holds free text, so nothing can be smuggled into a manifest.

`SealedProvenanceInputs` is what the writer is handed (`R-PROV-018`):
`component_id`, `owners`, `source_path`, `source_hash`,
`verifier_version`, and `verification_report` (a `VerificationReport`).
`characterization` is derived from the report: `overall` is the
report's `overall`, `criteria_total` the number of entries in its
`criteria`, `criteria_passed` those whose `result` is `"pass"`.
Every entry in the report's `criteria` MUST have a `result` of `"pass"`,
`"fail"`, or `"skipped"`, and the report's `overall` MUST be `"pass"` or
`"fail"`; anything else makes the inputs invalid (`R-PROV-019`).
