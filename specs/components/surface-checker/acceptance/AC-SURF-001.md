# AC-SURF-001

Covers: R-SURF-001
Kind: generated-test

```gherkin
Given a repo_root whose comp-widget has gen/widget/widget.py containing
  "import nosuchmodule_xyz"
When check_surface("comp-widget", repo_root) is called
Then ok is False and findings is exactly one finding of kind
  "import_error" whose message contains "nosuchmodule_xyz"

Given gen/widget/widget.py containing "X = 1" and no depends_on
When check_surface("comp-widget", repo_root) is called
Then ok is True and findings is []
```
