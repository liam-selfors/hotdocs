# AC-VERIFY-008

Covers: R-VERIFY-008
Kind: compiled

```gherkin
Given unchanged gen/<component>/ and acceptance.md, and a judge callable
  that returns the same result every time it is called
When verify runs twice
Then the two VerificationReports are identical
```
