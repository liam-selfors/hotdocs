# AC-CLI-007

Covers: R-CLI-007
Kind: generated-test

"The forwarded tokens" are the fake's recorded argv, as in `AC-CLI-003`.
Every call passes `cwd=<project>`, `tool_root=<a fake tool root>` and a
collector as `output_fn`.

```gherkin
Given a project whose gen/spec-linter/spec_linter.py is a fake usage
  component
When run(["lint", "--help"]) is called
Then it returns 0, the collector received exactly two lines, "hotdocs
  lint: validate the spec corpus" then "usage: fake [options]", nothing
  was written to stderr, and the forwarded tokens are
  ["--help", "--repo-root=<project>"]

Given the same project
When run(["lint", "--strict", "-h"]) is called
Then it returns 0, the collector received the same two lines, and the
  forwarded tokens are ["--strict", "-h", "--repo-root=<project>"]

Given a project whose gen/component-gate-runner/component_gate_runner.py
  and gen/provenance-tracker/provenance_tracker.py are fake usage
  components, and whose fake llm-endpoint load_config returns {provider
  "claude-cli", model "sonnet", base_url None, api_key_env None,
  timeout_seconds None}
When run(["generate", "comp-x", "--help"]) and run(["verify", "--help"])
  are called
Then each returns 0, the collectors' first lines are "hotdocs generate:
  generate and verify a component" and "hotdocs verify: is everything
  ready", the forwarded tokens are ["generate", "comp-x", "--help",
  "--repo-root=<project>"] and ["verify", "--help",
  "--repo-root=<project>"], and nothing was written to stderr

Given a project whose gen/spec-linter/spec_linter.py is the ordinary
  fake component, which prints nothing and returns 7
When run(["lint", "--help"]) is called
Then it returns 7 and the collector received no line
```
