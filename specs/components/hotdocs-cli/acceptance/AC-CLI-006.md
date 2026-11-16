# AC-CLI-006

Covers: R-CLI-006
Kind: generated-test

```gherkin
Given fakes returning 0, then 7
When main routes "lint" to each, from a project given with `cwd=<project>`
Then the exit codes are 0 and 7 (the tokens the fakes received are not asserted here)

Given main(["frobnicate"]), main(["--version"]), and a verb whose component file is missing (`cwd=<project>` again, with no
  fake for that verb in the project or in an empty fake tool root passed as `tool_root`)
When each is called
Then the exit codes are 2, 0, and 2

Given a fake whose main raises an exception of a class it defines itself,
  named ModelResolutionError, with the message "model 'x' names no provider"
When main routes "lint" to it
Then it returns 2 and stderr holds exactly one line, "usage error: model 'x'
  names no provider"

Given a fake whose main raises ValueError("boom")
When main routes "lint" to it
Then the ValueError propagates out of main
```
