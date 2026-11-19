# AC-SURF-007

Covers: R-SURF-006
Kind: generated-test

```gherkin
Given a repo_root with the planted wrapper interpreter, whose comp-tool
  interface/library.md ends with the line
  "Implements: `specs/architecture/cli-conventions.md`", whose
  gen/tool/tool.py starts with "import os" and
  "assert os.environ.get('HOTDOCS_WRAPPED') == '1'", and whose main(argv)
  prints "usage error: unknown argument" to stderr and returns 2 only
  when that variable is "1", else returns 0
When check_surface("comp-tool", repo_root) is called
Then ok is True and findings is []

Given the same repo_root whose planted python adapter's provision
  reports ok False with reason "python environment: no lock for you"
When check_surface("comp-tool", repo_root) is called
Then findings is exactly
  [{"kind": "environment", "message": "python environment: no lock for you"}]
```
