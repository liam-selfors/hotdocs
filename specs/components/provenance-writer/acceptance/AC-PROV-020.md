# AC-PROV-020

Covers: R-PROV-019
Kind: generated-test

Valid inputs as in AC-PROV-018 unless a scenario changes one thing. Each
"changed" case is its own call, and each raises InvalidSealedInputError and
writes nothing.

```gherkin
Given inputs are not a mapping or object at all (None, a list, a string),
  or lack each of component_id, owners, source_path, source_hash,
  verifier_version, verification_report in turn
When write_sealed_provenance is called for each
Then each call raises InvalidSealedInputError

Given one field is changed to a value below
Then each call raises InvalidSealedInputError:
  component_id 5, "Comp-foo", "foo" (with the argument matching it);
  owners "pipeline-team", [], [5], ["pipeline-team", ""], ["Pipeline"];
  source_path 5, "a b/", "../x/", "gen/foo/", "/abs/";
  source_hash 5, "sha256:" plus 63 hex digits, "sha256:" plus 64
    uppercase hex digits, "sha1:" plus 64 hex digits;
  verifier_version 5, "verifier-orchestrator@2", "other@2.0.0"

Given verification_report is None, a list, an object with overall "ok",
  an object with overall 5, an object whose criteria is not a list, an
  object whose criteria holds an entry with no result, or a report whose
  overall is "pass" but one criteria entry has result "skipped"
Then each call raises InvalidSealedInputError

Given a report whose overall is "fail" and whose criteria all have
  result "fail", and separately one with result "skipped" entries
Then each is written with overall "fail" and criteria_passed counting
  only the "pass" entries

Given source_path "pipeline/foo" with no trailing slash
Then it is written unchanged to .sealed-provenance.json under
  pipeline/foo/
```
