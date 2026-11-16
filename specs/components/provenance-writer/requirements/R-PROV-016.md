# R-PROV-016

**R-PROV-016** — Converting a nested upstream value (`license_scan`,
  `secret_scan`, `verification_report`) into the manifest's
  JSON-serializable form MUST handle every shape the duck-typing
  convention (`D94`) permits — a plain `dict`, a `dataclasses`-decorated
  instance, **or any other object that exposes its fields as plain
  attributes** (e.g. `types.SimpleNamespace`), never only
  `dict`/dataclass. Such an object is converted from its public,
  non-callable attributes, never left as the original object for
  `json.dumps` to reject (`D131`).
