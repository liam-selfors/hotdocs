# hotdocs-criterion: sha256:66f831fb40a66c1a6517f3b9f19e42927bc627f6f724354d05bcfd5be21fe32a
import importlib.util
import sys
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value and value[name] is not None
    return getattr(value, name, None) is not None


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _fake_test_author_source():
    return (
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    cid = bundle['criterion_id']\n"
        "    name = 'test_' + cid.lower().replace('-', '_') + '.py'\n"
        "    return {\n"
        "        'component_id': " + repr("capability") + ",\n"
        "        'criterion_id': cid,\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': " + repr("v1") + ",\n"
        "        'cache_hit': False,\n"
        "        'file': {\n"
        "            'path': " + repr("verification/capabilities/P-X/generated-test/") + " + name,\n"
        "            'content': " + repr("def test_x():\n    assert True\n") + ",\n"
        "        },\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )


def _fake_llm_endpoint_source():
    return (
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\n"
        "        'text': " + repr('{"result": "fail", "rationale": "because"}') + ",\n"
        "        'model': model,\n"
        "        'backend': " + repr("fake") + ",\n"
        "        'model_call_error': None,\n"
        "    }\n"
    )


def _scenario_section(scenario_id, kind):
    return (
        "### " + scenario_id + "\n"
        "\n"
        "Covers: P-X\n"
        "Kind: " + kind + "\n"
        "\n"
        "```gherkin\n"
        "Given the system is assembled\n"
        "When a user runs it\n"
        "Then it works\n"
        "```\n"
        "\n"
    )


def _build_repo(repo_root, scenarios):
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n",
    )
    _write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")

    body = (
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Capability X\n"
        "\n"
        "## Scenarios\n"
        "\n"
    )
    for scenario_id, kind in scenarios:
        body = body + _scenario_section(scenario_id, kind)
    _write(repo_root / "specs" / "product" / "x.md", body)

    _write(repo_root / "gen" / "test-author" / "test_author.py", _fake_test_author_source())
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", _fake_llm_endpoint_source())


def _passing_test_author(bundle):
    sid = field(bundle, "scenario_id")
    name = "test_" + sid.lower().replace("-", "_") + ".py"
    return {
        "component_id": "capability",
        "criterion_id": sid,
        "model": "fake-model",
        "seed": 0,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": "verification/capabilities/P-X/generated-test/" + name,
            "content": "def test_x():\n    assert True\n",
        },
        "model_call_error": None,
    }


def _failing_judge(bundle):
    return {"result": "fail", "rationale": "because"}


def test_mixed_scenarios_report_rationale_only_on_llm_judge_and_fail_overall(tmp_path):
    repo_root = tmp_path / "repo"
    _build_repo(
        repo_root,
        [("CS-X-001", "generated-test"), ("CS-X-002", "llm-judge")],
    )

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"],
        repo_root,
        judge=_failing_judge,
        test_author=_passing_test_author,
    )

    cap = field(report, "P-X")
    scenarios = list(field(cap, "scenarios"))
    assert len(scenarios) == 2

    by_kind = {field(s, "kind"): s for s in scenarios}
    assert set(by_kind) == {"generated-test", "llm-judge"}

    gen_entry = by_kind["generated-test"]
    judge_entry = by_kind["llm-judge"]

    assert field(gen_entry, "id") == "CS-X-001"
    assert field(judge_entry, "id") == "CS-X-002"

    if isinstance(gen_entry, dict):
        assert "rationale" not in gen_entry
    else:
        assert getattr(gen_entry, "rationale", None) is None

    assert field(judge_entry, "rationale") == "because"
    assert field(judge_entry, "result") == "fail"

    assert field(cap, "overall") == "fail"


def test_capability_without_scenarios_fails_with_empty_list(tmp_path):
    repo_root = tmp_path / "repo"
    _build_repo(repo_root, [])

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"],
        repo_root,
        judge=_failing_judge,
        test_author=_passing_test_author,
    )

    cap = field(report, "P-X")
    assert field(cap, "overall") == "fail"
    assert list(field(cap, "scenarios")) == []


def test_only_llm_judge_scenario_without_judge_is_skipped(tmp_path):
    repo_root = tmp_path / "repo"
    _build_repo(repo_root, [("CS-X-001", "llm-judge")])

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"],
        repo_root,
    )

    cap = field(report, "P-X")
    scenarios = list(field(cap, "scenarios"))
    assert len(scenarios) == 1
    entry = scenarios[0]
    assert field(entry, "id") == "CS-X-001"
    assert field(entry, "kind") == "llm-judge"
    assert field(entry, "result") == "skipped"
    assert field(cap, "overall") == "skipped"