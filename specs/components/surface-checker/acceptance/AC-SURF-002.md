# AC-SURF-002

Covers: R-SURF-002
Kind: generated-test

```gherkin
Given a repo_root whose comp-widget depends_on [comp-bar], gen/bar/bar.py
  defining fetch_one, and gen/widget/widget.py defining
  _load_dep(repo_root, slug), which loads gen/<slug>/<slug>.py with
  importlib.util and quotes no slug, and a function run(repo_root) whose
  body has the line "bar_mod = _load_dep(repo_root, 'bar')" and then uses
  "bar_mod.fetch_one(1)", "bar_mod.fetch_all()" and "bar_mod.__name__"
When check_surface("comp-widget", repo_root) is called
Then findings is exactly one dependency_name finding with message
  "bar has no fetch_all, which the candidate uses"

Given the first repo_root, with gen/widget/widget.py replaced by a
  module with a docstring holding "uses bar.gone_a()", the comment line
  "# bar.gone_b is not called", and a function load(directory) whose body
  is "spec = importlib.util.spec_from_file_location('bar',
  str(directory / 'bar.py'))", then "bar = importlib.util.module_from_spec(spec)",
  "spec.loader.exec_module(bar)" and "return bar.fetch_one(1)"
When check_surface("comp-widget", repo_root) is called
Then ok is True

Given that widget.py with its last line changed to
  "return bar.fetch_all()"
When check_surface("comp-widget", repo_root) is called
Then findings is exactly one dependency_name finding with message
  "bar has no fetch_all, which the candidate uses"

Given the same comp-widget, and comp-bar sealed with source_path
  legacy/bar/ holding bar.py that defines fetch_one and fetch_all, and no
  gen/bar/
When check_surface("comp-widget", repo_root) is called
Then ok is True
```
