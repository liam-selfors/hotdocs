# AC-INIT-002

Covers: R-INIT-002
Kind: generated-test

```gherkin
Given a fake tool root (with llm-endpoint, as in the fixtures) that also holds gen/a-b/a_b.py
  and a pyproject.toml whose [project] table has version = "9.8.7a1"
When init runs on an empty directory
Then <dir>/gen is an empty directory (the other entries R-INIT-001
  writes exist beside it), no pipeline directory exists,
  and .hotdocs-tool.json parses to exactly {"tool_version": "9.8.7a1"}

Given a fake tool root with no pyproject.toml
When init runs on an empty directory
Then .hotdocs-tool.json parses to exactly {"tool_version": "unknown"}

Given the second run
When init runs again
Then .hotdocs-tool.json has the same bytes and modification time

Given a target whose gen/ already holds a-b/ (the fake tool root's slug) and gen/mine/
When init runs
Then it exits 1 naming "gen/a-b" and not "gen/mine", and nothing at all was written

Given the target is the tool root itself
When init runs
Then it exits 1 and nothing was written
```
