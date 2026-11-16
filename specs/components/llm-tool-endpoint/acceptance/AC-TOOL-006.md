# AC-TOOL-006

Covers: R-TOOL-006
Kind: generated-test

```gherkin
Given ANTHROPIC_API_KEY is "secret-key-value" and urllib.request.urlopen
  replaced by a function that records each request and raises
  urllib.error.HTTPError with status <status> and body
  "vendor says no"
When run_tool_loop is called
Then exactly one request was recorded, stop is "error", the category is
  <category>, and neither "vendor says no" nor "secret-key-value"
  appears in the result's to_dict() rendered as JSON

Examples:
  | status | category   |
  | 401    | auth       |
  | 429    | rate_limit |
  | 504    | timeout    |
  | 500    | network    |
```
