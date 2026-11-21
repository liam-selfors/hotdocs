# AC-SLUG-001

Covers: R-SLUG-001
Kind: generated-test

```gherkin
Given the title "Hello, World!"
When slugify(title) is called
Then it returns "hello-world"

Given the title "  --Rust & Go: 2 Languages--  "
When slugify(title) is called
Then it returns "rust-go-2-languages"
```
