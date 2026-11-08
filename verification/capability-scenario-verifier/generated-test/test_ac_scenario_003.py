import capability_scenario_verifier


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _write_fixture(tmp_path, capability_id, capability_name, capability_body, slug):
    repo_root = tmp_path / "repo"

    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True)
    (product_dir / f"{capability_name}.md").write_text(capability_body)

    comp_dir = repo_root / "specs" / "components" / slug
    comp_dir.mkdir(parents=True)
    component_id = f"comp-{slug}"
    component_md = f"""---
id: {component_id}
title: Fixture Component {slug}
status: ratified
owners: [team-test]
realizes: [{capability_id}]
sealed: false
last_ratified_commit: 0000000
---

Fixture component realizing {capability_id}.
"""
    (comp_dir / "component.md").write_text(component_md)

    module_name = slug.replace("-", "_")
    gen_dir = repo_root / "gen" / slug
    gen_dir.mkdir(parents=True)
    (gen_dir / f"{module_name}.py").write_text("def run():\n    pass\n")

    return repo_root, component_id


def test_generated_test_and_llm_judge_scenarios(tmp_path):
    capability_body = """---
id: P-ALPHA
title: Alpha Capability
status: ratified
owners: [team-test]
last_ratified_commit: 0000000
---

### CS-ALPHA-001

Covers: P-ALPHA
Kind: generated-test

```gherkin
Given a widget
When it is used
Then it works
```

### CS-ALPHA-002

Covers: P-ALPHA
Kind: llm-judge

```gherkin
Given a widget
When it is judged
Then it is judged
```
"""
    repo_root, component_id = _write_fixture(
        tmp_path, "P-ALPHA", "alpha", capability_body, "alpha-comp"
    )

    def fake_test_author(bundle):
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-ALPHA/generated-test/test_cs_alpha_001.py",
                "content": "def test_x():\n    assert True\n",
            },
        }

    def fake_judge(bundle):
        return {"result": "fail", "rationale": "because"}

    report = capability_scenario_verifier.run_capability_scenarios(
        [component_id], repo_root, judge=fake_judge, test_author=fake_test_author
    )

    entry = _get(report, "P-ALPHA")
    assert entry is not None

    scenarios = _get(entry, "scenarios")
    assert len(scenarios) == 2

    generated_entries = [s for s in scenarios if _get(s, "kind") == "generated-test"]
    judge_entries = [s for s in scenarios if _get(s, "kind") == "llm-judge"]
    assert len(generated_entries) == 1
    assert len(judge_entries) == 1

    gen_entry = generated_entries[0]
    judge_entry = judge_entries[0]

    if isinstance(gen_entry, dict):
        assert "rationale" not in gen_entry
    else:
        assert not hasattr(gen_entry, "rationale")

    assert _get(gen_entry, "result") == "pass"
    assert _get(judge_entry, "rationale") == "because"
    assert _get(judge_entry, "result") == "fail"
    assert _get(entry, "overall") == "fail"


def test_capability_with_no_cs_scenario(tmp_path):
    capability_body = """---
id: P-BETA
title: Beta Capability
status: ratified
owners: [team-test]
last_ratified_commit: 0000000
---

No scenarios declared for this capability.
"""
    repo_root, component_id = _write_fixture(
        tmp_path, "P-BETA", "beta", capability_body, "beta-comp"
    )

    report = capability_scenario_verifier.run_capability_scenarios(
        [component_id], repo_root
    )

    entry = _get(report, "P-BETA")
    assert entry is not None
    assert _get(entry, "overall") == "fail"

    scenarios = _get(entry, "scenarios")
    assert len(scenarios) == 0


def test_llm_judge_scenario_without_judge_is_skipped(tmp_path):
    capability_body = """---
id: P-GAMMA
title: Gamma Capability
status: ratified
owners: [team-test]
last_ratified_commit: 0000000
---

### CS-GAMMA-001

Covers: P-GAMMA
Kind: llm-judge

```gherkin
Given a thing
When it is judged
Then it is judged
```
"""
    repo_root, component_id = _write_fixture(
        tmp_path, "P-GAMMA", "gamma", capability_body, "gamma-comp"
    )

    report = capability_scenario_verifier.run_capability_scenarios(
        [component_id], repo_root
    )

    entry = _get(report, "P-GAMMA")
    assert entry is not None

    scenarios = _get(entry, "scenarios")
    assert len(scenarios) == 1

    scenario_entry = scenarios[0]
    assert _get(scenario_entry, "result") == "skipped"
    assert _get(entry, "overall") == "skipped"