# AC-PROV-010

Covers: R-PROV-010
Kind: compiled

```gherkin
Given a completed write_provenance call
When both gen/<component>/.provenance.json and
  verification/<component>/.provenance.json are read back
Then their contents are byte-identical
```
