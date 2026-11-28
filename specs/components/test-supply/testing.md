# Testing test-supply

Every criterion writes its fixture under a fresh temporary `repo_root`
and plants stand-ins at the paths `supply` loads them from, so the real
dependencies are never used.

**The assembler stand-in.**
`<repo_root>/gen/spec-bundle-assembler/spec_bundle_assembler.py`
defines `assemble_criterion(component_id, criterion_id, repo_root)`
returning a dict with `criterion_text` `"c"`, `requirement_text` `"r"`,
`interface` `"i"`, `glossary` `"g"`, `testing` `""`, plus
`component_id`, `criterion_id` and `covers`. The correct header for it
is `# hotdocs-criterion: sha256:` followed by the SHA-256 hex of
`json.dumps({k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")}, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`
encoded UTF-8.

**The probe stand-in.** `<repo_root>/gen/test-probe/test_probe.py`
defines `probe(test_source, criterion_bundle, module_name, **kwargs)`
returning an object with `ok`, `findings` (dicts with `kind`,
`severity`, `line`, `message`) and `to_dict()`; it appends each call's
`module_name` and `kwargs` as one JSON line to `<repo_root>/probe.log`.
It returns `ok` true with no findings unless the criterion says
otherwise; a failing finding has `"severity": "error"`.

**The test author stand-in.** A callable taking the bundle, appending
one line to `<repo_root>/author.log` per call, and returning a dict
with `model` `"m"`, `seed` `0`, `prompt_version` `"v1"`, `cache_hit`
`False`, `model_call_error` and `file` (`{"path": "x", "content": <text>}`
or `None`) as the criterion says.

The component is `comp-foo`, its criterion `AC-FOO-001`; its committed
test is `<repo_root>/verification/foo/generated-test/test_ac_foo_001.py`.
