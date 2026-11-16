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

Given load_config returns that configuration, and main(["lint"]) and main(["decision","new","x"])
When called
Then neither forwarded token list contains a --model and stderr holds no "using model" line

Given load_config returns that configuration, and main(["assist","--changed=R-X-1"]) and main(["verify"])
When called
Then each forwarded token list ends with "--repo-root=<project>" then "--model=claude-cli:sonnet", and stderr
  holds "hotdocs: using model claude-cli:sonnet from hotdocs.toml (pass --no-model to skip)" once per call

Given load_config returns that configuration, and main(["assist","--changed=R-X-1","--no-model"]) and
  main(["generate","comp-x","--no-model"])
When called
Then the forwarded tokens are the given ones without "--no-model", followed by "--repo-root=<project>" only

Given main(["lint","--no-model"])
When called
Then the forwarded tokens are ["--no-model","--repo-root=<project>"]
```
