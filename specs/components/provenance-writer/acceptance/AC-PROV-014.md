# AC-PROV-014

Covers: R-PROV-014
Kind: generated-test

```gherkin
Given a plain dict-shaped ProvenanceInputs (not a ProvenanceInputs
  instance), with every field a real-shaped value
When write_provenance runs
Then it writes a manifest without raising, identical in every field
  to the manifest written from an equivalent ProvenanceInputs
  instance built from the same values

Given a ProvenanceInputs instance (not a dict)
When write_provenance runs
Then it writes a manifest without raising
```
