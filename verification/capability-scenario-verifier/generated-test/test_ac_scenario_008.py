# hotdocs-criterion: sha256:17ed1097952481866452eb0073d8e8b6e2b5495d5962d5472f91e8808adb3fa0
import sys
from pathlib import Path

import pytest

import capability_scenario_verifier


SCENARIO_ID = "CS-X-001"
CAPABILITY_ID = "P-X"
GOOD_PATH = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Planted python adapter.
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # Realizing component, not sealed, with code under gen/foo/.
    write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
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
        "def value():\n"
        "    return 7\n",
    )

    # Capability with one generated-test scenario.
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
        "Given a foo component\n"
        "When its value is read\n"
        "Then the value is seven\n"
        "```\n",
    )
    return repo_root


def make_author(outcome, calls):
    def test_author(bundle):
        calls.append(bundle)
        return outcome

    return test_author


def run(repo_root, outcome, calls):
    return capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, judge=None, test_author=make_author(outcome, calls)
    )


def capability_entry(report):
    if isinstance(report, dict):
        return report[CAPABILITY_ID]
    return getattr(report, CAPABILITY_ID)


def scenario_result(report):
    entry = capability_entry(report)
    scenarios = field(entry, "scenarios")
    matching = [s for s in scenarios if field(s, "id") == SCENARIO_ID]
    assert len(matching) == 1, scenarios
    return field(matching[0], "result"), field(entry, "overall")


def test_failing_generated_test_is_fail_and_written(tmp_path):
    repo_root = make_repo(tmp_path)
    content = "def test_x():\n    assert False\n"
    outcome = {"model_call_error": None, "file": {"path": GOOD_PATH, "content": content}}
    calls = []
    report = run(repo_root, outcome, calls)
    result, overall = scenario_result(report)
    assert len(calls) >= 1
    assert result == "fail"
    assert overall == "fail"
    written = repo_root / GOOD_PATH
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == content


@pytest.mark.parametrize("which", ["dotdot", "absolute", "notverification"])
def test_bad_path_is_fail_and_nothing_written(tmp_path, which):
    repo_root = make_repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    if which == "dotdot":
        returned = "../escape.py"
        targets = [repo_root.parent / "escape.py", (repo_root / returned).resolve()]
    elif which == "absolute":
        target = outside / "escape.py"
        returned = str(target)
        targets = [target]
    else:
        returned = "notverification/x.py"
        targets = [repo_root / "notverification" / "x.py"]
    outcome = {
        "model_call_error": None,
        "file": {"path": returned, "content": "def test_x():\n    assert True\n"},
    }
    calls = []
    report = run(repo_root, outcome, calls)
    result, overall = scenario_result(report)
    assert len(calls) >= 1
    assert result == "fail"
    assert overall == "fail"
    for target in targets:
        assert not target.exists(), str(target)


@pytest.mark.parametrize("kind", ["model_call_error", "no_file"])
def test_model_call_error_or_no_file_is_fail(tmp_path, kind):
    repo_root = make_repo(tmp_path)
    if kind == "model_call_error":
        outcome = {
            "model_call_error": {"category": "network", "message": "connection failed"},
            "file": None,
        }
    else:
        outcome = {"model_call_error": None, "file": None}
    calls = []
    report = run(repo_root, outcome, calls)
    result, overall = scenario_result(report)
    assert len(calls) >= 1
    assert result == "fail"
    assert overall == "fail"


def test_passing_test_runs_with_component_code_on_pythonpath(tmp_path):
    repo_root = make_repo(tmp_path)
    content = (
        "import foo_mod\n"
        "\n"
        "\n"
        "def test_value():\n"
        "    assert foo_mod.value() == 7\n"
    )
    outcome = {"model_call_error": None, "file": {"path": GOOD_PATH, "content": content}}
    calls = []
    report = run(repo_root, outcome, calls)
    result, overall = scenario_result(report)
    assert len(calls) >= 1
    assert result == "pass"
    assert overall == "pass"
    assert (repo_root / GOOD_PATH).is_file()