# AC-VERIFY-028

Covers: R-VERIFY-014
Kind: generated-test

```gherkin
Given DEFAULT_TEST_TIMEOUT set to 5 and comp-qux with one current
  cached test that starts a child with subprocess.Popen(...,
  start_new_session=True) writing its pid to <tmp>/child.pid and
  sleeping 600 seconds, then sleeps 600 seconds itself
When verify runs
Then that criterion is fail, verify returns within 60 seconds, and
  2 seconds later the pid in child.pid is not running
```
