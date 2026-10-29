# AC-PROV-015

Covers: R-PROV-015
Kind: generated-test

```gherkin
Given argv ["provenance", "write", "comp-foo", "--repo-root=<tmp>"]
  and a valid ProvenanceInputs JSON document on stdin
When main(argv) runs
Then it returns 0 and both required .provenance.json files exist
  under <tmp>

Given argv missing a required upstream result in the stdin JSON
  (write_provenance raises MissingInputError)
When main(argv) runs
Then it returns 1 and writes nothing

Given argv ["provenance", "write"] with no component-id
When main(argv) runs
Then it returns 2

Given argv ["provenance", "write", "comp-foo", "--bogus-flag"]
When main(argv) runs
Then it returns 2

Given argv ["provenance", "write", "comp-foo"] and malformed JSON on
  stdin
When main(argv) runs
Then it returns 2
```
