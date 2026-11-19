# R-PROVCHECK-003

**R-PROVCHECK-003** — MUST report a definitive miss — never a partial
  or approximate result — when `gen/<component>/.provenance.json` is
  absent, when its `spec_bundle_hash` or any `gate_versions` entry does
  not match the supplied ones, on `R-PROVCHECK-009`'s asset misses, or
  when they match but R-PROVCHECK-002's
  `llm-judge`/
  `VAR-TRUST-JUDGE-PROVENANCE` exception applies. A miss here always
  means the caller MUST run the full generation/verification/scan
  sequence for that component — there is no partial-credit result that
  trusts some of a manifest's fields while re-deriving others.
