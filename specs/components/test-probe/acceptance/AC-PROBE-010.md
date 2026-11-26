# AC-PROBE-010

Covers: R-PROBE-009
Kind: generated-test

```gherkin
Given test_source with one test taking the fixture browser and calling
  browser.open("x.html")
When probe(test_source, {}, "slugify", drivers=["browser"]) is called
Then ok is True, findings is [] and tests_reached is 1

When probe(test_source, {}, "slugify") is called
Then ok is False and the one finding has kind "test_bug"
```
