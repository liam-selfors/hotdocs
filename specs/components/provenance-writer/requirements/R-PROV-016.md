# R-PROV-016

**R-PROV-016** — Converting a nested upstream value (`license_scan`,
  `secret_scan`, `verification_report`) into the manifest's
  JSON-serializable form MUST handle every shape this corpus's
  duck-typing convention (`D94`) permits — a plain `dict`, a
  `dataclasses`-decorated instance, **or any other object that
  exposes its fields as plain attributes** (e.g. `types.SimpleNamespace`,
  or any fake built the same way) — never only `dict`/`dataclasses.
  is_dataclass()`. A value whose shape doesn't match any of these MUST
  still be converted by reading its public, non-callable attributes
  directly, not left as the original object for `json.dumps` to reject.

  Found via a real cold-generation regression (`D131`): a candidate's
  own `_to_jsonable` handled `dict`/`list`/`tuple`/dataclass but fell
  through unchanged for a `SimpleNamespace`-shaped `license_scan`,
  crashing `json.dumps` with `TypeError: Object of type SimpleNamespace
  is not JSON serializable` — `R-PROV-014` only required dual access
  when *reading* a field off `inputs` itself, not converting an
  already-read nested object for writing.
