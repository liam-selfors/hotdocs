# AC-GEN-025

Covers: R-GEN-015
Kind: generated-test

```gherkin
Given repo_root holds comp-widget-maker declaring
  assets [fake:static/app.txt] and the fake kind (testing.md)
When generate is called with a mock model
Then the prompt the mock receives contains "widget_maker.py" and
  "static/app.txt" before its first "## SPEC" line
```
