# AC-SURF-003

Covers: R-SURF-003
Kind: generated-test

```gherkin
Given a repo_root whose comp-tool interface/library.md ends with the line
  "Implements: `specs/architecture/cli-conventions.md`" and whose
  gen/tool/tool.py main(argv) prints "usage error: unknown argument" to
  stderr and returns 2 for any argument
When check_surface("comp-tool", repo_root) is called
Then ok is True

Given main instead raises ValueError for an unknown argument
When check_surface("comp-tool", repo_root) is called
Then findings is exactly one cli_usage finding whose message contains
  "exit 1" and "traceback"

Given the same raising main and an interface/library.md with no
  Implements line
When check_surface("comp-tool", repo_root) is called
Then ok is True
```
