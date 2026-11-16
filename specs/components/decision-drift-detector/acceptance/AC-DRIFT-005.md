# AC-DRIFT-005

Covers: R-DRIFT-005
Kind: generated-test

```gherkin
Given argv ["decision-drift", "--repo-root=<a real git repo with no
  drift>", "--format=json"]
When main(argv) runs
Then it returns 0 and prints a JSON report with an empty entries list

Given argv ["decision-impact", "D1", "--repo-root=<a real git repo>"]
When main(argv) runs
Then it returns 0 and prints a human-readable report

Given argv ["decision-impact", "--repo-root=<a real git repo>"] with
  no decision-id
When main(argv) runs
Then it returns 2

Given argv ["decision-drift", "--repo-root=<a path that is not a git
  repository>"]
When main(argv) runs
Then it returns 2

Given the current working directory is itself a real git repo with
  no drift, and argv ["decision-drift"] with no --repo-root at all
When main(argv) runs
Then it returns 0, defaulting --repo-root to the current git
  repository root

Given argv ["decision-drift", "--repo-root=<a real git repo>",
  "--format=bogus"]
When main(argv) runs
Then it returns 2
```
