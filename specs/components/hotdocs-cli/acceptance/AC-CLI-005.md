# AC-CLI-005

Covers: R-CLI-005
Kind: generated-test

```gherkin
Given a tool root holding gen/hotdocs-init/hotdocs_init.py, a fake whose main records its argv and its keyword
  arguments, and an empty project directory with no gen/ at all
When main(["init","dir","--yes"], tool_root=<tool root>, input_fn=f, output_fn=g, env=e, cwd=c) is called
Then the fake received ["dir","--yes"] and exactly the keywords tool_root, input_fn, output_fn, env, cwd
  with those values; no "--repo-root" was appended; and its return value is the exit code

Given main(["init"]) with none of those keywords given
When called
Then the fake received input as input_fn, print as output_fn, and the process environment and
  current directory for env and cwd
```
