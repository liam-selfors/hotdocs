# AC-KJS-001

Covers: R-KJS-001
Kind: generated-test

```gherkin
Given the module kind_javascript
When its constants are read
Then KIND == "javascript", GATE_VERSION == "kind-javascript@1.0.0",
  and AssetError is a class with issubclass(AssetError, Exception) True
  and AssetError("x") has str "x"
```
