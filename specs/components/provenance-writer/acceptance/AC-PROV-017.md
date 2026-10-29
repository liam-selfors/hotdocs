# AC-PROV-017

Covers: R-PROV-017
Kind: generated-test

```gherkin
Given the provenance_writer module
When ProvenanceInputs is looked up as an attribute of it
Then it exists, is a dataclass, and constructing one with every
  documented field by keyword succeeds

Given a ProvenanceInputs instance built that way, passed to
  write_provenance
When write_provenance runs
Then it writes a manifest without raising
```
