# AC-PROV-022

Covers: R-PROV-020
Kind: generated-test

```gherkin
Given ProvenanceInputs whose generation_result has mode "agentic",
  transcript_sha256 "sha256:t", turns 9, tool_calls 30, isolation
  "sandbox-exec" and a transcript field holding "RAW-TRANSCRIPT",
  gate_versions with generator "generator@3.0.0+v11", attempts 2, and
  attempt_history of two entries, the first carrying an extra key
  "notes" with "EXTRA-NOTE"
When write_provenance(component_id, inputs, repo_root) is called
Then the manifest's generation is {"mode": "agentic", "generator_version":
  "generator@3.0.0+v11", "transcript_sha256": "sha256:t", "turns": 9,
  "tool_calls": 30, "isolation": "sandbox-exec"}, attempts is 2,
  attempt_history has two entries each with exactly the keys number,
  outcome, retry_feedback, error_category, failed_requirements and
  transcript_sha256, and neither "RAW-TRANSCRIPT" nor "EXTRA-NOTE"
  appears in the manifest file

Given inputs with no attempt_history and a generation_result with no mode
When write_provenance is called
Then attempt_history is [] and generation's mode is "single"
```
