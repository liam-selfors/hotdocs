# AC-AUTHOR-029

Covers: R-AUTHOR-029
Kind: generated-test

```gherkin
Given the CLI fixture, the stub returning criterion_id "AC-FOO-001",
  file {"path": "p.py", "content": "x"}, model_call_error None
When main runs ["comp-foo", "AC-FOO-001", "--model", "m", "--repo-root", <root>]
Then it returns 0, stdout is "AC-FOO-001: wrote p.py\n", the stub got seed 0,
  and with "--format=json" stdout's JSON has "criterion_id" "AC-FOO-001"
And with model_call_error {"category": "network", "message": "down"} it
  returns 1 and prints "AC-FOO-001: model_call_error network: down\n"

When main runs ["comp-foo"], or the valid call plus "--format=xml",
  "--seed=x", "--bogus" or a final "--model"
Then each returns 2, stdout is empty, and stderr starts "usage error: "
  plus that case's cause
```
