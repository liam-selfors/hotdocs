# AC-DRV-005

Covers: R-DRV-004
Kind: generated-test

```gherkin
Given the module loaded
When guidance() is called
Then it returns a dict whose only key is "test_author", whose value
  starts with "Drive pages only through the `browser` fixture." and
  ends with "`pytest.raises(Exception, match=...)` on the message."
```
