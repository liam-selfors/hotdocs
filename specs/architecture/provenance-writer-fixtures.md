---
id: arch-provenance-writer-fixtures
title: Calling write_provenance, and What It Writes Where
status: draft
owners: [pipeline-team]
depends_on: []
---

# Calling `write_provenance`, and what it writes where

## Purpose

States the input shapes, required inputs, field sources and file layout
of `provenance-writer`'s `write_provenance`, so the generator and every
criterion's test author work from the same facts.

## Input shapes

`write_provenance` MUST accept `inputs` as a `ProvenanceInputs` dataclass
or a plain dict of the same fields, and each nested value
(`generation_result`, `verification_report`, `license_scan_result`,
`secret_scan_result`, each `attempt_history` entry) as a dataclass, any
object with those attributes, or a plain dict. Every field is read with
dual dict-or-attribute access. A field absent from a dict or object reads
as `null`; extra keys and attributes are ignored, never written.

## Required inputs

`write_provenance` MUST raise `MissingInputError` (defined in its module),
writing no manifest, when any of `component_id`, `generation_result`,
`license_scan_result`, `secret_scan_result`, `provenance_hit`, `attempts`
or `gate_versions` is absent or `null`, or when `verification_report` is
`null` and `generation_result.files` is non-empty. No other input is
required: a `generation_result` of `{"files": {}}`, scan results of `{}`,
`provenance_hit` `false`, `attempts` `1`, `gate_versions` `{}` and
`verification_report` `null` form a valid minimal call.

## Field sources

- `spec_bundle_hash`, `prompt_version` and `retry_feedback` are copied from
  `generation_result`'s fields of the same name; `model_pin` from
  `generation_result.model`.
- `license_scan`, `secret_scan`, `verification_report`, `gate_versions`
  and `provenance_hit` are copied from the inputs `license_scan_result`,
  `secret_scan_result`, `verification_report`, `gate_versions` and
  `provenance_hit`.
- `generation`, `attempts` and `attempt_history` follow `R-PROV-020`:
  `generation.mode` is `"single"` when `generation_result.mode` is absent
  or `null`. A transcript MAY arrive as `generation_result.transcript`;
  it, and every `generation_result` field not named here, is never
  written.
- `assets` is `verification_report.assets` copied verbatim, order kept,
  and `[]` when `verification_report` is `null` or has no `assets` or a
  `null` one (`R-PROV-022`).
- `pipeline_version` is a module constant; `generated_at` is the current
  UTC time as `YYYY-MM-DDTHH:MM:SSZ`; `verification_run_id` is
  `"<slug>-attempt-<attempts>"`.
- A copied field absent from its source is written as `null`.

## Files

`<slug>` is `component_id` without its `comp-` prefix. `write_provenance`
reads nothing under `repo_root`: an empty directory is a valid
`repo_root`. It creates `gen/<slug>/` and `verification/<slug>/` (with
parents) when absent and writes byte-identical JSON to
`<repo_root>/gen/<slug>/.provenance.json` and
`<repo_root>/verification/<slug>/.provenance.json`. Every rule on manifest
content applies to both files.
