# AC-GEN-023

Covers: R-GEN-021
Kind: generated-test

```gherkin
Given a bundle for comp-widget-maker and a mock model whose reply holds
  one complete file block for widget_maker.py and no END REPLY line
When generate is called
Then model_call_error has category "truncated_response", files is
  empty, gen/widget-maker/ is not created, and nothing is cached

Given a mock reply with a complete block for widget_maker.py, a BEGIN
  FILE line for helpers.py with no END FILE line, and an END REPLY line
When generate is called
Then model_call_error has category "truncated_response" and its
  message contains "helpers.py"

Given a mock reply with a complete block for notes.py only, ending in
  the END REPLY line
When generate is called
Then model_call_error has category "missing_module" and nothing is
  written or cached

Given a mock reply with complete blocks for widget_maker/__init__.py and
  widget_maker/core.py, ending in the END REPLY line
When generate is called
Then the result has no model_call_error and both files are written
```
