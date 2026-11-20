# AC-INIT-007

Covers: R-INIT-007
Kind: generated-test

```gherkin
Given run(["--bogus"]), run(["--provider"]), run(["a","b"]),
  run(["--provider","nope"]), and run(["--provider=openai","--model"])
When each is called
Then each returns 2, nothing is written under <dir> (a __pycache__ that
  importing llm-endpoint leaves under the tool root is not a write to
  <dir>), and the "nope" message lists the PROVIDERS keys

Given run(["--provider","openai","--api-key-env","sk-abc123"]) and "--api-key-env 9X"
When called
Then each returns 2, nothing is written, and no output contains "sk-abc123"

Given run(["--provider","claude-cli","--base-url","http://h"]), then "--api-key-env","K",
  then "--auth","token", and run(["--provider","openai","--model","m","--auth","login"])
When called
Then each returns 2

Given run(["--provider","openai-compatible","--base-url","http://h"]) with no --model,
  and the same with --model m but no --base-url
When called
Then each returns 2

Given run(["--provider","openai","--yes","<dir>"]) with the flags in either order and both flag forms
When called
Then it returns 0

Given the module's main
When its parameters are inspected, and main(["--bogus"]) is called
Then the parameter names are exactly ["argv"], and the call returns 2
```
