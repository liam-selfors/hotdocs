# AC-CLI-001

Covers: R-CLI-001
Kind: generated-test

```gherkin
Given a project with fake components for every row of the verb table except "init"
When main is called for each row's verb words followed by "x" and "--flag"
Then the row's fake was called once with the tokens after the first strip tokens
  (so ["x","--flag","--repo-root=<project>"] after strip 1; ["generate","x",...]
  for strip 0; ["x",...] for "docs-site build"), the exit code is 7, and the
  longest prefix won ("track ui build" never reached "track feedback")

Given a fake whose main raises SystemExit(3), SystemExit(None), then SystemExit("boom")
When main routes to it three times (the fake ignores its tokens)
Then it returns 3, 0, and 1

Given two projects whose "lint" fakes differ, called one after the other in one process
When main routes "lint" in each
Then each call reaches its own project's fake (compare which fake ran, not
  the tokens it received, which always end with the `--repo-root` token)

Given a project with no gen/spec-linter and a fake tool root whose "lint" fake
  logs to the project's calls.log
When main(["lint"], tool_root=<fake tool root>, cwd=<project>) is called
Then the tool root's fake ran and the exit code is 7; and once the project has
  its own "lint" fake, the project's fake runs instead
```
