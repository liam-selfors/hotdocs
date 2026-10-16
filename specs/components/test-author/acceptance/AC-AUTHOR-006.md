# AC-AUTHOR-006

Covers: R-AUTHOR-006
Kind: compiled

```gherkin
Given a successful author_test call for a component
When the written file's path is inspected
Then it is under verification/<component>/generated-test/ and not under
  gen/<component>/ or criterion-compiler's own output directory
```
