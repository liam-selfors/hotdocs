# AC-PROV-015

Covers: R-PROV-015
Kind: generated-test

```gherkin
Given argv ["provenance", "write", "comp-foo", "--repo-root=<tmp>"]
  and a valid ProvenanceInputs JSON document on stdin
When main(argv) runs
Then it returns 0 and both required .provenance.json files exist
  under <tmp>

Given argv ["provenance", "write", "comp-foo", "--repo-root=<tmp>"]
  and a stdin JSON document that is otherwise valid but has no
  license_scan_result key (write_provenance raises MissingInputError)

Every "otherwise valid" document here has a generation_result with
non-empty files and a populated verification_report: a null report
beside non-empty files is itself missing input
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

Given argv ["provenance", "write", "comp-foo", "--repo-root", "<tmp>"]
  and a valid document on stdin
When main(argv) runs
Then it returns 0 and both files exist under <tmp>

Given argv ["provenance", "write", "comp-foo", "--repo-root"]
Then it returns 2

Given argv ["provenance", "write", "comp-foo", "comp-bar"]
Then it returns 2
```
