# AC-SLUG-003

Covers: R-SLUG-003
Kind: generated-test

```gherkin
Given each of the titles "", "   " and "!!!"
When slugify(title) is called
Then it raises ValueError whose message contains "empty"
```
