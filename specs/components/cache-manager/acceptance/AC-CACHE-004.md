# AC-CACHE-004

Covers: R-CACHE-004
Kind: generated-test

```gherkin
Given the backing store at VAR-CACHE-STORE-URL is unreachable
When get is called with any key
Then it returns Miss rather than raising an exception
```
