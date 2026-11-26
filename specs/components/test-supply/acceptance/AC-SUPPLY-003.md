# AC-SUPPLY-003

Covers: R-SUPPLY-003
Kind: generated-test

```gherkin
Given a committed test with the correct header, a probe stand-in
  returning ok False with one finding of kind "undefined_name" and
  severity "error" for the committed file's source only, and a test
  author stand-in returning a file with the correct header
When supply is called with assets ["static/app.js"] and drivers
  ["browser"]
Then author.log has one line, authored is true, failure_origin is None,
  and each probe.log line has module_name "foo", assets
  ["static/app.js"] and drivers ["browser"]

Given a probe stand-in returning ok False with findings of kinds
  "undefined_name", "syntax_error" and "undefined_name", each severity
  "error", for every source
When supply is called
Then author.log has one line, failure_origin is "test", path is None
  and failure_message is
  "test failed its probe: undefined_name, syntax_error"
```
