# AC-SUPPLY-001

Covers: R-SUPPLY-001
Kind: generated-test

```gherkin
Given a committed test whose first line is the correct header
When supply("comp-foo", "AC-FOO-001", repo_root, test_author=stand_in)
  is called
Then path is the committed file, authored is false, test_authoring is
  None, failure_origin is None, and author.log does not exist

Given a committed test whose first line is no header, or the header
  with 64 zeros in place of the hash, and a stand-in returning a file
  whose first line is the correct header
When supply is called
Then author.log has one line, authored is true, and path is a file
  outside verification/ holding the returned content
```
