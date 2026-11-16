# AC-SIZE-004

Covers: R-SIZE-004
Kind: generated-test

```gherkin
Given a component whose Purpose section is 160 words long, with no
  decision citation anywhere in it
When check(repo_root) runs
Then it fails with R-SIZE-004 naming the hard-fail threshold —
  confirming this rule fires independently of R-LINT-024, on length
  alone
```
