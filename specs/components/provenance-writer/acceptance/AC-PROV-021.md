# AC-PROV-021

Covers: R-PROV-010
Kind: generated-test

```gherkin
Given a repo_root where gen/foo/.provenance.json and
  verification/foo/.provenance.json already exist with stale content
When write_provenance runs for comp-foo with new inputs
Then both files hold exactly the new manifest

Given a repo_root where pipeline/foo/.sealed-provenance.json already
  exists with stale content
When write_sealed_provenance runs with new valid inputs
Then it holds exactly the new manifest, and no second file was created

Given generation_result.files is empty (or None) and verification_report
  is None
When write_provenance runs
Then it writes a manifest whose verification_report is null

Given generation_result.files is non-empty and verification_report is
  None
When write_provenance runs
Then it raises MissingInputError and writes nothing
```
