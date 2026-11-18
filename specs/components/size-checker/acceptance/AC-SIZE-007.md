# AC-SIZE-007

Covers: R-SIZE-003
Kind: generated-test

```gherkin
Given one acceptance file of 300 words and a second acceptance file of
  520 words in the same component
When check(repo_root) runs
Then the first file gets a warn R-SIZE-003 finding and the second a
  fail R-SIZE-003 finding, each with its own path as file and naming
  its own word count
```
