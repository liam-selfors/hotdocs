# R-PROVCHECK-003

**R-PROVCHECK-003** — MUST report a definitive miss — never a partial
  or approximate result — when `gen/<component>/.provenance.json` is
  absent, when its `spec_bundle_hash` or any `gate_versions` entry does
  not match the supplied ones, or when they match but R-PROVCHECK-002's
  `llm-judge`/
  `VAR-TRUST-JUDGE-PROVENANCE` exception applies. A miss here always
  means the caller MUST run the full generation/verification/scan
  sequence for that component — there is no partial-credit result that
  trusts some of a manifest's fields while re-deriving others; the one
  piece of nuance that kind of split would require (which specific
  criteria to trust) is exactly the complexity this component is
  deliberately not taking on, per D4/D6's precedent against building
  machinery nothing has asked for yet.
