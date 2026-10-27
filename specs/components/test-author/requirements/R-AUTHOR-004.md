# R-AUTHOR-004

**R-AUTHOR-004** — Before calling any model, MUST check `cache-manager`
  using a key derived from `(criterion content hash, gate_inputs_hash,
  gate_version, model)` — mirrors `generator`'s R-GEN-005 exactly, at
  criterion granularity instead of component granularity.

  **`gate_version`'s `<gate_type>@<semver>` prefix MUST be exactly
  `generated_test`** — `cache-manager`'s own six-entry `gate_type`
  registry (`interface/data/CachedResult.md`) names the *kind of cached
  artifact*, not the producing component; it has no `test_author` entry
  at all. `generator`'s own `gate_version` happens to equal its gate
  type only because the component and the artifact kind share a name
  by coincidence — not a pattern to copy here. A real candidate did
  exactly that, using `test_author@<version>` and crashing on its own
  first cache write (`D56`).
