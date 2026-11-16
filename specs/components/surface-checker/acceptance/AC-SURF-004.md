# AC-SURF-004

Covers: R-SURF-004
Kind: generated-test

```gherkin
Given a repo_root whose comp-widget depends_on [comp-zed, comp-alpha],
  each with a module defining nothing, a widget.py using zed.b, zed.a and
  alpha.c (after "import zed" and "import alpha" guarded by try/except
  ImportError), an interface/library.md with the line
  "Implements: `specs/architecture/cli-conventions.md`", and a main(argv)
  that prints nothing and returns 0
When check_surface("comp-widget", repo_root) is called
Then findings' kinds and messages are, in order: dependency_name
  "zed has no a, which the candidate uses", dependency_name "zed has no b,
  which the candidate uses", dependency_name "alpha has no c, which the
  candidate uses", then cli_usage "exit 0, no usage error line"; and to_dict()["ok"] is False
```
