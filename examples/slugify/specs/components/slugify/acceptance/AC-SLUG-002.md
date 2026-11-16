# AC-SLUG-002

Covers: R-SLUG-002
Kind: generated-test

```gherkin
Given the title "Café Déjà Vu"
When slugify(title) is called
Then it returns "cafe-deja-vu"

Given the title "Tokyo 日本 Guide"
When slugify(title) is called
Then it returns "tokyo-guide"
```
