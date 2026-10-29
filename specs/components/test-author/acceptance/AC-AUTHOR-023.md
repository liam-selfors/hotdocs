# AC-AUTHOR-023

Covers: R-AUTHOR-023
Kind: generated-test

```gherkin
Given any bundle
When author_test builds its prompt
Then the prompt instructs that a wall-clock write-time window check
  must truncate its own before/after bounds to the documented field
  format's own precision, never compare a truncated-on-write
  timestamp against microsecond-precision bounds directly
```
