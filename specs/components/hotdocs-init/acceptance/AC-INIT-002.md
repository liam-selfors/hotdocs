# AC-INIT-002

Covers: R-INIT-002
Kind: generated-test

```gherkin
Given a fake tool root (with llm-endpoint, as in the fixtures) that also holds gen/a-b/a_b.py, gen/c/__pycache__/x.pyc, and pipeline/criterion-compiler/criterion_compiler.py
When init runs on an empty directory
Then gen/a-b/a_b.py and pipeline/criterion-compiler/criterion_compiler.py are copies, no __pycache__ exists anywhere under the project (copied or created by loading llm-endpoint),
  and .hotdocs-tool.json holds tool_version "0.1.0", a sorted vendored list of those paths, and a content_hash starting "sha256:"

Given the second run
When init runs again
Then vendored paths are reported skipped and not recopied

Given a target already holding gen/a-b/ and no stamp
When init runs
Then it exits 1 naming "gen/a-b", and nothing at all was written

Given the target is the tool root itself
When init runs
Then it exits 1 and nothing was written
```
