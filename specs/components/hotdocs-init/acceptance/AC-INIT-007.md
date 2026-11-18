# AC-INIT-007

Covers: R-INIT-007
Kind: generated-test

```gherkin
Given main(["--bogus"]), main(["--provider"]), main(["a","b"]),
  main(["--provider","nope"]), and main(["--provider=openai","--model"])
When each is called
Then each returns 2, nothing is written under <dir> (a __pycache__ that
  importing llm-endpoint leaves under the tool root is not a write to
  <dir>), and the "nope" message lists the PROVIDERS keys

Given main(["--provider","openai","--api-key-env","sk-abc123"]) and "--api-key-env 9X"
When called
Then each returns 2, nothing is written, and no output contains "sk-abc123"

Given main(["--provider","claude-cli","--base-url","http://h"]), then "--api-key-env","K",
  then "--auth","token", and main(["--provider","openai","--model","m","--auth","login"])
When called
Then each returns 2

Given main(["--provider","openai-compatible","--base-url","http://h"]) with no --model,
  and the same with --model m but no --base-url
When called
Then each returns 2

Given main(["--provider","openai","--yes","<dir>"]) with the flags in either order and both flag forms
When called
Then it returns 0
```
