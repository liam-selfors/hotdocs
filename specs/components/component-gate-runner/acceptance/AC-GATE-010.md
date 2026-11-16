# AC-GATE-010

Covers: R-GATE-010
Kind: generated-test

```gherkin
Given the faked dependencies, a passing loop, and a hotdocs.toml under
  repo_root holding "[generate]\nmax_attempts = 5\nmode = \"agentic\"\n"
When main(["generate", "comp-foo", "--model=m", "--repo-root=<repo_root>"])
  runs
Then run_attempts received max_attempts 5 and mode "agentic"

Given the same hotdocs.toml
When main runs with "--max-attempts=1" and "--mode=single" as well
Then run_attempts received max_attempts 1 and mode "single"

Given a hotdocs.toml whose [generate] mode is "turbo", or
  "--max-attempts=0", or "--mode=turbo"
When main runs generate for comp-foo with --model=m
Then it returns 2, its first stderr line starts "usage error: ", and
  run_attempts was never called
```
