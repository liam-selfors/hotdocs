# AC-REVIEW-005

Covers: R-REVIEW-005
Kind: generated-test

```gherkin
Given a lint-clean synthetic corpus with AC-FOO-001, and a mock
  llm_backend replying '{"writable": false, "gaps": [{"kind": "guess",
  "missing": "the unit", "proposed_text": "x is in metres",
  "target_file": "specs/components/foo/interface/library.md"}]}' to every
  prompt
When check(["AC-FOO-001"], repo_root, model="mock", llm_backend=backend,
  write_proposals=True) is called
Then proposals is [".hotdocs/proposals/AC-FOO-001.md"], and that file's
  text is "# Proposals for AC-FOO-001\n\n- kind: guess\n  missing: the
  unit\n  target_file: specs/components/foo/interface/library.md\n
  proposed_text: x is in metres\n"

Given the same corpus and backend
When check is called the same way but without write_proposals
Then proposals is empty and no .hotdocs/proposals/ directory exists
```
