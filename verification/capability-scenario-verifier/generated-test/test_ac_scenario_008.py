# hotdocs-criterion: sha256:d5937dffd19624d0a68f1763506c1d37b7ce12907fe1e2ae0bcbeeaba3bbfaee
import os
from pathlib import Path

import pytest

import capability_scenario_verifier


GOOD_PATH = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def capability_entry(report, p_id):
    if isinstance(report, dict):
        return report[p_id]
    try:
        return report[p_id]
    except (TypeError, KeyError):
        return getattr(report, p_id)


def scenario_result(report, p_id, scenario_id):
    entry = capability_entry(report, p_id)
    scenarios = field(entry, "scenarios")
    for s in scenarios:
        if field(s, "id") == scenario_id:
            return field(s, "result")
    raise AssertionError("scenario " + repr(scenario_id) + " not in report: " + repr(report))


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    repo_root.mkdir(parents=True, exist_ok=True)

    # Component realizing P-X, unsealed, code under gen/foo/
    write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    write(
        repo_root / "gen" / "foo" / "foo_mod.py",
        "def value():\n    return 7\n",
    )

    # Capability with one generated-test scenario
    write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Capability X\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a thing\n"
        "When it runs\n"
        "Then it works\n"
        "```\n",
    )

    # Fake dependency modules (flat shape), matching documented signatures
    write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    return {\n"
        "        'component_id': bundle.get('component_id'),\n"
        "        'criterion_id': bundle.get('criterion_id'),\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {'path': " + repr(GOOD_PATH) + ", 'content': " + repr("def test_x():\n    assert True\n") + "},\n"
        "        'model_call_error': None,\n"
        "    }\n",
    )
    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {'text': 'PASS', 'model': model, 'backend': 'fake', 'model_call_error': None}\n",
    )
    return repo_root


def make_author(outcome):
    def test_author(bundle):
        return outcome
    return test_author


def test_failing_generated_test_is_fail_and_written(tmp_path):
    repo_root = build_fixture(tmp_path / "repo")
    content = "def test_x():\n    assert False\n"
    author = make_author({"model_call_error": None, "file": {"path": GOOD_PATH, "content": content}})

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=author
    )

    assert scenario_result(report, "P-X", "CS-X-001") == "fail"
    assert field(capability_entry(report, "P-X"), "overall") == "fail"
    written = repo_root / GOOD_PATH
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == content


@pytest.mark.parametrize("kind", ["dotdot", "absolute", "notverification"])
def test_bad_path_is_fail_and_nothing_written(tmp_path, kind):
    repo_root = build_fixture(tmp_path / "repo")
    if kind == "dotdot":
        returned = "../escape.py"
        target = (repo_root / ".." / "escape.py").resolve()
    elif kind == "absolute":
        outside = tmp_path / "outside"
        outside.mkdir()
        target = outside / "x.py"
        returned = str(target)
    else:
        returned = "notverification/x.py"
        target = repo_root / "notverification" / "x.py"

    assert not target.exists()
    author = make_author(
        {"model_call_error": None, "file": {"path": returned, "content": "def test_x():\n    assert True\n"}}
    )

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=author
    )

    assert scenario_result(report, "P-X", "CS-X-001") == "fail"
    assert not target.exists()


@pytest.mark.parametrize(
    "outcome",
    [
        {"model_call_error": {"category": "network", "message": "connection failed"}, "file": None},
        {"model_call_error": None, "file": None},
    ],
    ids=["model_call_error", "no_file"],
)
def test_model_call_error_or_no_file_is_fail(tmp_path, outcome):
    repo_root = build_fixture(tmp_path / "repo")
    author = make_author(outcome)

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=author
    )

    assert scenario_result(report, "P-X", "CS-X-001") == "fail"


def test_realizing_component_code_on_pythonpath(tmp_path):
    repo_root = build_fixture(tmp_path / "repo")
    content = "import foo_mod\n\n\ndef test_x():\n    assert foo_mod.value() == 7\n"
    author = make_author({"model_call_error": None, "file": {"path": GOOD_PATH, "content": content}})

    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, test_author=author
    )

    assert scenario_result(report, "P-X", "CS-X-001") == "pass"
    assert (repo_root / GOOD_PATH).is_file()