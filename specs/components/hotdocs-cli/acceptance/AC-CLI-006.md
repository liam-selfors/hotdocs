# AC-CLI-006

Covers: R-CLI-006
Kind: generated-test

```gherkin
Given fakes returning 0, then 7
When main routes "lint" to each, from a project given with `cwd=<project>`
Then the exit codes are 0 and 7 (the tokens the fakes received are not asserted here)

Given main(["frobnicate"]), main(["--version"]), and a verb whose component file is missing (`cwd=<project>` again, with no
  fake for that verb)
When each is called
Then the exit codes are 2, 0, and 2
```
