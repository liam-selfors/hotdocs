# AC-TRACK-015

Covers: R-TRACK-007
Kind: generated-test

```gherkin
Given a GenerationResult dict and a VerificationReport dict holding one
  failing criterion whose failure_detail is {"message": "m", "actual":
  {"b", "a"}, "raw": b"x"}
When write_attempt_record(component_id, generation, verification,
  spec_bundle_hash, repo_root) is called
Then it does not raise, the one file under
  .hotdocs/attempts/<component_id>/ parses as JSON, and in it that
  criterion's failure_detail actual is ["a", "b"] and raw is "x"
```
