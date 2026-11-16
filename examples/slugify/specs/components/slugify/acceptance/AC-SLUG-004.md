# AC-SLUG-004

Covers: R-SLUG-004
Kind: generated-test

```gherkin
Given the title "alpha beta gamma"
When slugify(title, max_length=11) is called
Then it returns "alpha-beta"

Given the title "alpha beta gamma"
When slugify(title, max_length=80) is called
Then it returns "alpha-beta-gamma"

Given the title "abc"
When slugify(title, max_length=0) is called
Then it raises ValueError whose message contains "max_length"
```
