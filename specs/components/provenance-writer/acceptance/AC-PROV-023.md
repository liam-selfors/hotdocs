# AC-PROV-023

Covers: R-PROV-021
Kind: generated-test

```gherkin
Given valid ProvenanceInputs whose VerificationReport has one failing
  generated-test criterion whose failure_detail is {"message": "m",
  "expected": "e", "actual": {"b", "a"}}, and whose failure_detail also
  holds "raw": b"x" and "where": pathlib.Path("p")
When write_provenance(component_id, inputs, repo_root) is called
Then it does not raise, and in the written verification manifest that
  criterion's failure_detail actual is ["a", "b"], raw is "x" and where
  is "p"

Given the same inputs whose failure_detail actual is an instance of a
  class defining __slots__ = ("x",)
When write_provenance(component_id, inputs, repo_root) is called
Then it does not raise, and that actual is a string beginning "<"
```
