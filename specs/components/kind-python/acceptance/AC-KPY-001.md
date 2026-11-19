# AC-KPY-001

Covers: R-KPY-001
Kind: generated-test

```gherkin
Given the module kind_python
When its constants are read
Then KIND == "python", GATE_VERSION == "kind-python@1.0.0",
  and AssetError is a class with issubclass(AssetError, Exception) True
  and AssetError("x") has str "x"
```
