from pathlib import Path

import capability_scenario_verifier


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _has(obj, key):
    if isinstance(obj, dict):
        return key in obj
    return hasattr(obj, key)


def _scenario_by_id(scenarios, scenario_id):
    for entry in scenarios:
        if _get(entry, "id") == scenario_id:
            return entry
    raise AssertionError(f"no scenario entry with id {scenario_id!r} in {scenarios!r}")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


FOO_COMPONENT = """---
id: comp-foo-component
title: Foo Component
status: draft
owners: [qa@example.com]
realizes: [P-FOO]
sealed: true
source_path: fake/foo-component
---

# Foo Component

Fixture component realizing P-FOO.
"""

FOO_CAPABILITY = """---
id: P-FOO
title: Foo Capability
status: draft
owners: [qa@example.com]
---

# Foo Capability

### CS-FOO-001

Covers: P-FOO
Kind: generated-test

```gherkin
Given a widget capability
When the generated test for it runs
Then it passes
```

### CS-FOO-002

Covers: P-FOO
Kind: llm-judge

```gherkin
Given a judged capability behavior
When an llm-judge evaluates it
Then the verdict is recorded
```
"""

NOCS_COMPONENT = """---
id: comp-nocap-component
title: No-Scenario Component
status: draft
owners: [qa@example.com]
realizes: [P-NOCS]
sealed: true
source_path: fake/nocap-component
---

# No-Scenario Component

Fixture component realizing P-NOCS.
"""

NOCS_CAPABILITY = """---
id: P-NOCS
title: No Scenario Capability
status: draft
owners: [qa@example.com]
---

# No Scenario Capability

This capability intentionally declares no CS- scenario section.
"""

SKIP_COMPONENT = """---
id: comp-skip-component
title: Skip Component
status: draft
owners: [qa@example.com]
realizes: [P-SKIP]
sealed: true
source_path: fake/skip-component
---

# Skip Component

Fixture component realizing P-SKIP.
"""

SKIP_CAPABILITY = """---
id: P-SKIP
title: Skip Capability
status: draft
owners: [qa@example.com]
---

# Skip Capability

### CS-SKIP-001

Covers: P-SKIP
Kind: llm-judge

```gherkin
Given a capability with only an llm-judge scenario
When no judge callable is supplied
Then that scenario is skipped
```
"""


def test_generated_test_pass_and_llm_judge_fail_yields_overall_fail(tmp_path):
    repo_root = tmp_path
    _write(repo_root / "specs" / "components" / "foo-component" / "component.md", FOO_COMPONENT)
    _write(repo_root / "specs" / "product" / "foo.md", FOO_CAPABILITY)

    def fake_test_author(bundle):
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-FOO/generated-test/test_cs_foo_001.py",
                "content": "def test_cs_foo_001():\n    assert True\n",
            },
        }

    def fake_judge(bundle):
        return {"result": "fail", "rationale": "because"}

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo-component"], repo_root, judge=fake_judge, test_author=fake_test_author
    )

    entry = _get(report, "P-FOO")
    assert entry is not None
    scenarios = _get(entry, "scenarios")
    assert len(scenarios) == 2

    generated_entry = _scenario_by_id(scenarios, "CS-FOO-001")
    assert _get(generated_entry, "kind") == "generated-test"
    assert _get(generated_entry, "result") == "pass"
    assert not _has(generated_entry, "rationale")

    judge_entry = _scenario_by_id(scenarios, "CS-FOO-002")
    assert _get(judge_entry, "kind") == "llm-judge"
    assert _get(judge_entry, "result") == "fail"
    assert _get(judge_entry, "rationale") == "because"

    assert _get(entry, "overall") == "fail"


def test_capability_with_no_cs_scenario_is_fail_with_empty_scenarios(tmp_path):
    repo_root = tmp_path
    _write(repo_root / "specs" / "components" / "nocap-component" / "component.md", NOCS_COMPONENT)
    _write(repo_root / "specs" / "product" / "nocap.md", NOCS_CAPABILITY)

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-nocap-component"], repo_root
    )

    entry = _get(report, "P-NOCS")
    assert entry is not None
    assert _get(entry, "overall") == "fail"
    assert list(_get(entry, "scenarios")) == []


def test_llm_judge_only_scenario_without_judge_is_skipped(tmp_path):
    repo_root = tmp_path
    _write(repo_root / "specs" / "components" / "skip-component" / "component.md", SKIP_COMPONENT)
    _write(repo_root / "specs" / "product" / "skip.md", SKIP_CAPABILITY)

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-skip-component"], repo_root
    )

    entry = _get(report, "P-SKIP")
    assert entry is not None
    scenarios = _get(entry, "scenarios")
    assert len(scenarios) == 1

    skip_entry = _scenario_by_id(scenarios, "CS-SKIP-001")
    assert _get(skip_entry, "kind") == "llm-judge"
    assert _get(skip_entry, "result") == "skipped"

    assert _get(entry, "overall") == "skipped"