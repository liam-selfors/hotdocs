# R-PROVCHECK-003

**R-PROVCHECK-003** — MUST report a definitive miss — never a partial
  or approximate result — when `gen/<component>/.provenance.json` is
  absent, when its `spec_bundle_hash` or any `gate_versions` entry does
  not match the supplied ones, on `R-PROVCHECK-009`'s asset misses, or
  when they match but R-PROVCHECK-002's
  `llm-judge`/
  `VAR-TRUST-JUDGE-PROVENANCE` exception applies. No result trusts
  some of a manifest's fields while re-deriving others.
