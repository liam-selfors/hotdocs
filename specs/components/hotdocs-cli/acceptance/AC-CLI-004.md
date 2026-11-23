# AC-CLI-004

Covers: R-CLI-004
Kind: generated-test

```gherkin
Given any project and a fake tool root whose pyproject.toml holds a
  [project] table with version = "9.8.7a1"
When run([]), run(["--help"]), run(["-h"]), run(["help"]) are called, each with tool_root=<that fake tool root>
Then each returns 0 and prints "hotdocs 9.8.7a1" and every verb of the table, "init" included, with its summary

Given the same fake tool root
When run(["--version"], tool_root=<it>) is called
Then it prints "hotdocs 9.8.7a1" and returns 0

Given a fake tool root with no pyproject.toml, then one whose
  pyproject.toml is "not toml [", then one whose pyproject.toml holds
  only a [tool.x] table
When run(["--version"], tool_root=<each>) is called
Then each prints "hotdocs unknown" and returns 0

Given run(["frobnicate"])
When called
Then it returns 2 and stderr holds "unknown verb: frobnicate" and the verb list

Given a project and an empty fake tool root, neither with gen/spec-linter,
  then a project whose fake has no main
When run(["lint"], tool_root=<fake tool root>) is called
Then each returns 2; the first message names "gen/spec-linter/spec_linter.py"
```
