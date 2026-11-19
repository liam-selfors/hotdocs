# AC-GEN-026

Covers: R-GEN-021
Kind: generated-test

```gherkin
Given repo_root holds comp-widget-maker declaring
  assets [fake:static/app.txt] and the fake kind (testing.md)
When check_assets("comp-widget-maker", files, repo_root=repo_root) is
  called with files
  {"widget_maker.py": "", "static/app.txt": "ok", "b.md": "", "a.json": ""}
Then it returns ("malformed_layout", ["undeclared file: a.json",
  "undeclared file: b.md"]) and nothing new exists under repo_root

Given files {"widget_maker/__init__.py": "", "static/app.txt": "ok"}
When check_assets is called
Then it returns (None, [])

Given files {"widget_maker.py": "", "bad.py": "", "static/app.txt": "ok"}
When check_assets is called
Then it returns ("malformed_layout", ["bad.py:1: SyntaxError: x"])

Given files {"widget_maker.py": ""}
When check_assets is called
Then it returns ("missing_asset", ["missing asset: static/app.txt"])

Given a bare repo_root with no component.md and files
  {"widget_maker.py": ""}
When check_assets is called
Then it returns (None, [])

Given the first fixture, then repo_root/NO_ENV created
When check_asset_environment("comp-widget-maker", repo_root=repo_root)
  is called before and after creating it
Then it returns (None, []) and then
  ("environment", ["fake needs fakeprog >= 2"]), the fake python
  adapter's provision called first; with the kind
  nosuchkind instead it returns
  ("environment", ["unknown asset kind: nosuchkind"])
```
