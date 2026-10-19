# AC-PROV-001

Covers: R-PROV-001
Kind: compiled

```gherkin
Given a complete set of ProvenanceInputs
When write_provenance runs
Then the written manifest's top-level keys exactly match SPEC_GUIDELINES.md
  §7's field list — no extra keys, no missing ones
```
