# AC-GATE-007

Covers: R-GATE-007
Kind: generated-test

```gherkin
Given comp-foo's component.md declares sealed: true with a source_path
When run_component_gates is called
Then provenance-checker, spec-bundle-assembler, generator,
  write_attempt_record, and write_provenance were never called, verify
  and both scanners were called once each, and provenance_hit is false

Given verify returns overall "fail" for that sealed component
When run_component_gates is called
Then blocked is true with block_reason "verification_failed"
```
