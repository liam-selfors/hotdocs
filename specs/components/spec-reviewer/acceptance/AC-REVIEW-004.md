# AC-REVIEW-004

Covers: R-REVIEW-004
Kind: generated-test

```gherkin
Given a lint-clean synthetic corpus with AC-FOO-001 and AC-FOO-002, and
  a mock llm_backend that records each prompt; for a prompt holding
  "AC-FOO-001" it replies 'Here: {"writable": false, "gaps": [{"kind":
  "unstated_behavior", "missing": "negative x", "proposed_text": "MUST
  raise ValueError", "target_file": "R-FOO-001.md"}, {"kind": "other",
  "missing": "m", "proposed_text": "p", "target_file": "t"}]} done', and
  otherwise it replies "not json"
When check(["comp-foo"], repo_root, model="mock", llm_backend=backend)
  is called
Then the backend's prompts that were not for the lint judge number
  exactly two, the one holding "AC-FOO-001" does not hold "AC-FOO-002",
  and each holds, on one line, the sentence R-REVIEW-004 gives that
  starts "The pipeline fixes the test framework (pytest)" and ends
  "never report any of these as a gap.";
  writable is {"AC-FOO-001": False, "AC-FOO-002": None}; gaps holds
  exactly the one unstated_behavior gap with criterion_id "AC-FOO-001";
  findings holds one model_unparseable finding for AC-FOO-002; and
  degraded is false
```
