import capability_scenario_verifier as csv


FRONTMATTER_COMPONENT = """---
id: comp-widget
title: Widget
status: ratified
owners: [lselfors@gmail.com]
realizes: [P-FOO]
sealed: true
source_path: vendor/widget/
last_ratified_commit: 0000000
---

Widget component.
"""

FRONTMATTER_PRODUCT = """---
id: P-FOO
title: Foo capability
status: ratified
owners: [lselfors@gmail.com]
last_ratified_commit: 0000000
---

### CS-FOO-001

Covers: P-FOO
Kind: generated-test

```gherkin
Given a widget
When it is used
Then it works
```
"""

FAKE_FILE = {
    "path": "verification/capabilities/P-FOO/generated-test/test_cs_foo_001.py",
    "content": "def test_x():\n    assert True\n",
}


def build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    component_dir = repo_root / "specs" / "components" / "widget"
    component_dir.mkdir(parents=True)
    (component_dir / "component.md").write_text(FRONTMATTER_COMPONENT)

    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True)
    (product_dir / "foo.md").write_text(FRONTMATTER_PRODUCT)

    return repo_root


def get(obj, key):
    if isinstance(obj, dict):
        return obj[key]
    return getattr(obj, key)


def bundle_key_set(bundle):
    if isinstance(bundle, dict):
        return set(bundle.keys())
    return set(vars(bundle).keys())


def find_scenario(report, capability_id, scenario_id):
    capability = get(report, capability_id)
    for scenario in get(capability, "scenarios"):
        if get(scenario, "id") == scenario_id:
            return scenario
    raise AssertionError(f"scenario {scenario_id} not found in report for {capability_id}")


def test_generated_test_scenario_dispatches_fresh_on_every_call(tmp_path):
    repo_root = build_repo(tmp_path)
    invocations = []

    def fake_test_author(bundle):
        invocations.append(get(bundle, "scenario_id"))
        return {"model_call_error": None, "file": dict(FAKE_FILE)}

    csv.run_capability_scenarios(["comp-widget"], repo_root, test_author=fake_test_author)
    csv.run_capability_scenarios(["comp-widget"], repo_root, test_author=fake_test_author)

    assert invocations == ["CS-FOO-001", "CS-FOO-001"]


def test_bundle_passed_to_test_author_has_exact_keys(tmp_path):
    repo_root = build_repo(tmp_path)
    received = []

    def fake_test_author(bundle):
        received.append(bundle)
        return {"model_call_error": None, "file": dict(FAKE_FILE)}

    csv.run_capability_scenarios(["comp-widget"], repo_root, test_author=fake_test_author)

    assert len(received) == 1
    bundle = received[0]
    assert bundle_key_set(bundle) == {
        "capability_id",
        "scenario_id",
        "covers",
        "kind",
        "gherkin",
        "file",
    }
    assert get(bundle, "capability_id") == "P-FOO"
    assert get(bundle, "scenario_id") == "CS-FOO-001"
    assert get(bundle, "kind") == "generated-test"


def test_generated_test_scenario_fails_without_test_author(tmp_path):
    repo_root = build_repo(tmp_path)

    report = csv.run_capability_scenarios(["comp-widget"], repo_root)

    scenario = find_scenario(report, "P-FOO", "CS-FOO-001")
    assert get(scenario, "result") == "fail"