# AC-SURF-008

Covers: R-SURF-007
Kind: generated-test

```gherkin
Given a repo_root whose comp-widget has depends_on [comp-bar, comp-baz],
  gen/bar/bar.py defining fetch_one and helper,
  specs/components/bar/interface/library.md holding exactly the line
  "fetch_one(x) -> int", gen/baz/baz.py defining baz_only and no
  specs/components/baz/interface/ files, and gen/widget/widget.py
  defining _load_dep(repo_root, slug), which loads
  gen/<slug>/<slug>.py with importlib.util and quotes no slug, a function
  one(repo_root) whose body has "mod = _load_dep(repo_root, 'bar')" then
  uses "mod.fetch_one(1)" and "mod.helper()", and a function
  two(repo_root) whose body has "mod = _load_dep(repo_root, 'baz')" then
  uses "mod.baz_only()"
When check_surface("comp-widget", repo_root) is called
Then findings is exactly one finding, kind "dependency_undocumented",
  message "bar does not document helper, which the candidate uses": no
  finding names baz_only against bar or fetch_one or helper against baz,
  and baz, having no interface files, gets no dependency_undocumented
  finding
```
