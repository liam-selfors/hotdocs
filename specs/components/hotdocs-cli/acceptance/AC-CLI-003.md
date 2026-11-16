# AC-CLI-003

Covers: R-CLI-003
Kind: generated-test

In every scenario "the forwarded tokens" are the fake's recorded argv; the
`--repo-root=<project>` token that `R-CLI-002` appends is part of them.

```gherkin
Given a project whose fake llm-endpoint load_config returns {provider "claude-cli",
  model "sonnet", base_url None, api_key_env None, timeout_seconds None}
When main(["generate","comp-x"]) and main(["author-test","comp-x","AC-X-1"]) are called
Then each fake received the given tokens, then "--repo-root=<project>", then a final "--model=claude-cli:sonnet"

Given main(["generate","comp-x","--model","m"]) and main(["generate","comp-x","--model=m"])
When called
Then the forwarded tokens are the given ones followed by "--repo-root=<project>" only: no second --model

Given load_config returns None, then raises ValueError("bad"), for main(["generate","comp-x"])
When called
Then the forwarded tokens are ["generate","comp-x","--repo-root=<project>"] each time, and the second call prints "bad" to stderr

Given load_config returns a configuration, and "verify", "lint", and "assist" calls
When called
Then none of the forwarded token lists contains a --model
```
