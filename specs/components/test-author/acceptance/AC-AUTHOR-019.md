# AC-AUTHOR-019

Covers: R-AUTHOR-019
Kind: generated-test

```gherkin
Given a bundle and a spy backend recording every keyword argument it
  is called with
When author_test is called with a non-default seed
Then the backend is called with only prompt and model as positional
  arguments and no seed keyword argument at all
```
