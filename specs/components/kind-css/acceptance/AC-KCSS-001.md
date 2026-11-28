# AC-KCSS-001

Covers: R-KCSS-001
Kind: generated-test

```gherkin
Given the module kind_css and its source, read from
  Path(kind_css.__file__) and parsed with ast.parse
When its names and every Import and ImportFrom node are examined
Then KIND == "css", GATE_VERSION == "kind-css@1.0.0", AssetError is a
  subclass of Exception, and no imported module name, before its first
  ".", is subprocess, socket, http, urllib, multiprocessing or one
  starting "hotdocs"
```
