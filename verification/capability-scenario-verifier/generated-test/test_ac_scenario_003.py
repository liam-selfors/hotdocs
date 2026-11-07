import pathlib

import capability_scenario_verifier


_MISSING = object()


def _get(obj, key, default=_MISSING):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
    elif hasattr(obj, key):
        return getattr(obj, key)
    if default is _MISSING:
        raise AssertionError(f"missing field {key!r} on {obj!r}")
    return default


def _has(obj, key):
    if isinstance(obj, dict):
        return key in obj
    return hasattr(obj, key)


def _find_by_kind(scenarios, kind):
    for entry in scenarios:
        if _get(entry, "kind") == kind:
            return entry
    raise AssertionError(f"no scenario entry with kind={kind!r} in {scenarios!r}")


def _write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _write_component(repo_root, comp_id, slug, realizes):
    realizes_str = "[" + ", ".join(realizes) + "]"
    content = (
        "---\n"
        f"id: {comp_id}\n"
        f"title: {comp_id} component\n"
        "status: draft\n"
        "owners: [test-owner]\n"
        "sealed: false\n"
        f"realizes: {realizes_str}\n"
        "---\n"
        "\n"
        f"{comp_id} component body.\n"
    )
    _write(repo_root / "specs" / "components" / slug / "component.md", content)
    module_name = slug.replace("-", "_")
    _write(repo_root / "gen" / slug / f"{module_name}.py", "def noop():\n    pass\n")


def _write_capability(repo_root, name, cap_id, body):
    content = (
        "---\n"
        f"id: {cap_id}\n"
        f"title: {cap_id} capability\n"
        "status: draft\n"
        "owners: [test-owner]\n"
        "---\n"
        "\n"
        f"{body}\n"
    )
    _write(repo_root / "specs" / "product" / f"{name}.md", content)


def test_generated_test_and_llm_judge_scenarios_mix_to_fail(tmp_path):
    repo_root = tmp_path
    _write_component(repo_root, "comp-widget1", "widget1", realizes=["P-FOO"])
    _write_capability(
        repo_root,
        "foo",
        "P-FOO",
        body=(
            "### CS-FOO-001\n"
            "\n"
            "Covers: P-FOO\n"
            "Kind: generated-test\n"
            "\n"
            "```gherkin\n"
            "Given a widget\n"
            "When it is used\n"
            "Then it works\n"
            "```\n"
            "\n"
            "### CS-FOO-002\n"
            "\n"
            "Covers: P-FOO\n"
            "Kind: llm-judge\n"
            "\n"
            "```gherkin\n"
            "Given a widget\n"
            "When it is judged\n"
            "Then it is acceptable\n"
            "```\n"
        ),
    )

    def fake_test_author(bundle):
        return {
            "model_call_error": None,
            "file": {
                "path": "verification/capabilities/P-FOO/generated-test/test_cs_foo_001.py",
                "content": "def test_x():\n    assert True\n",
            },
        }

    def fake_judge(bundle):
        return {"result": "fail", "rationale": "because"}

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-widget1"], repo_root, judge=fake_judge, test_author=fake_test_author
    )

    cap = _get(report, "P-FOO")
    scenarios = _get(cap, "scenarios")
    assert len(scenarios) == 2

    generated_entry = _find_by_kind(scenarios, "generated-test")
    assert _get(generated_entry, "id") == "CS-FOO-001"
    assert _get(generated_entry, "result") == "pass"
    assert not _has(generated_entry, "rationale")

    judge_entry = _find_by_kind(scenarios, "llm-judge")
    assert _get(judge_entry, "id") == "CS-FOO-002"
    assert _get(judge_entry, "result") == "fail"
    assert _get(judge_entry, "rationale") == "because"

    assert _get(cap, "overall") == "fail"


def test_capability_with_no_declared_scenario_fails_with_empty_list(tmp_path):
    repo_root = tmp_path
    _write_component(repo_root, "comp-widget2", "widget2", realizes=["P-BAR"])
    _write_capability(
        repo_root,
        "bar",
        "P-BAR",
        body="Bar capability has no scenarios declared yet.\n",
    )

    report = capability_scenario_verifier.run_capability_scenarios(["comp-widget2"], repo_root)

    cap = _get(report, "P-BAR")
    assert _get(cap, "overall") == "fail"
    assert list(_get(cap, "scenarios")) == []


def test_llm_judge_only_scenario_without_judge_is_skipped(tmp_path):
    repo_root = tmp_path
    _write_component(repo_root, "comp-widget3", "widget3", realizes=["P-BAZ"])
    _write_capability(
        repo_root,
        "baz",
        "P-BAZ",
        body=(
            "### CS-BAZ-001\n"
            "\n"
            "Covers: P-BAZ\n"
            "Kind: llm-judge\n"
            "\n"
            "```gherkin\n"
            "Given a widget\n"
            "When it is judged\n"
            "Then it is acceptable\n"
            "```\n"
        ),
    )

    report = capability_scenario_verifier.run_capability_scenarios(["comp-widget3"], repo_root)

    cap = _get(report, "P-BAZ")
    scenarios = _get(cap, "scenarios")
    assert len(scenarios) == 1
    entry = scenarios[0]
    assert _get(entry, "id") == "CS-BAZ-001"
    assert _get(entry, "result") == "skipped"
    assert _get(cap, "overall") == "skipped"