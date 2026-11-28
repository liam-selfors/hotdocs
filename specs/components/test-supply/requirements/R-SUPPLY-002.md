# R-SUPPLY-002

**R-SUPPLY-002** — When the committed test is missing or stale, `supply`
  MUST call `test_author` with the bundle and write the returned
  `file["content"]` under the criterion test filename into a fresh
  temporary directory. A `model_call_error` whose `category` is
  `network`, `timeout` or `rate_limit` gets one more call (`D319`); any
  other, or a second one, gives `failure_origin` `"test"` and
  `failure_message` `test authoring failed: <category>: <message>`. With
  no `test_author`, a missing or stale test gives
  `test authoring failed: none: no test author`.
