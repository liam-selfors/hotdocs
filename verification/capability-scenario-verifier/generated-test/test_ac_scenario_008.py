# hotdocs-criterion: sha256:23a503bcd86f6d0f691c098586302fd39405d0396c5c424a782f6ba1b018b574
import sys
from pathlib import Path

import pytest

import capability_scenario_verifier


GOOD_PATH = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def capability_entry(report, capability_id):
    if isinstance(report, dict):
        return report[capability_id]
    return getattr(report, capability_id)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_repo(repo_root):
    repo_root.mkdir(parents=True, exist_ok=True)

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

    # Fake test-author dependency, matching its documented signature/shape.
    write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    return {\n"
        "        \"component_id\": \"comp-foo\",\n"
        "        \"criterion_id\": bundle[\"criterion_id\"],\n"
        "        \"model\": model,\n"
        "        \"seed\": seed,\n"
        "        \"prompt_version\": \"v1\",\n"
        "        \"cache_hit\": False,\n"
        "        \"file\": {\"path\": " + repr(GOOD_PATH) + ",\n"
        "                 \"content\": " + repr("def test_x():\n    assert True\n") + "},\n"
        "        \"model_call_error\": None,\n"
        "        \"repair_attempts\": 0,\n"
        "        \"probe_findings\": [],\n"
        "    }\n",
    )

    # Fake llm-endpoint dependency.
    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\"text\": \"pass\", \"model\": model, \"backend\": \"fake\",\n"
        "            \"model_call_error\": None}\n",
    )

    # Realizing component.
    write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n",
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
        "title: X\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# X\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a foo\n"
        "When value is read\n"
        "Then it is 7\n"
        "```\n",
    )
    return repo_root


def make_author(outcome):
    def test_author(bundle):
        return outcome

    return test_author


def run(repo_root, outcome):
    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, judge=None, test_author=make_author(outcome)
    )
    entry = capability_entry(report, "P-X")
    scenarios = list(field(entry, "scenarios"))
    matching = [s for s in scenarios if field(s, "id") == "CS-X-001"]
    assert len(matching) == 1, scenarios
    return entry, matching[0]


def test_failing_generated_test_fails_and_file_is_written(tmp_path):
    repo_root = build_repo(tmp_path / "repo")
    outcome = {
        "model_call_error": None,
        "file": {"path": GOOD_PATH, "content": "def test_x():\n    assert False\n"},
    }
    entry, scenario = run(repo_root, outcome)
    assert field(scenario, "result") == "fail"
    assert field(entry, "overall") == "fail"
    written = repo_root / GOOD_PATH
    assert written.is_file()
    assert written.read_text() == "def test_x():\n    assert False\n"


@pytest.mark.parametrize("which", ["dotdot", "absolute", "notverification"])
def test_bad_path_fails_and_nothing_written(tmp_path, which):
    repo_root = build_repo(tmp_path / "repo")
    if which == "dotdot":
        returned = "../escape.py"
        target = (repo_root / "..").resolve() / "escape.py"
    elif which == "absolute":
        other = tmp_path / "separate"
        other.mkdir()
        target = other / "escape.py"
        returned = str(target)
    else:
        returned = "notverification/x.py"
        target = repo_root / "notverification" / "x.py"
    assert not target.exists()
    outcome = {
        "model_call_error": None,
        "file": {"path": returned, "content": "def test_x():\n    assert True\n"},
    }
    entry, scenario = run(repo_root, outcome)
    assert field(scenario, "result") == "fail"
    assert not target.exists()


@pytest.mark.parametrize("which", ["model_call_error", "no_file"])
def test_model_call_error_or_no_file_fails(tmp_path, which):
    repo_root = build_repo(tmp_path / "repo")
    if which == "model_call_error":
        outcome = {
            "model_call_error": {"category": "network", "message": "connection failed"},
            "file": None,
        }
    else:
        outcome = {"model_call_error": None, "file": None}
    entry, scenario = run(repo_root, outcome)
    assert field(scenario, "result") == "fail"


def test_test_runs_with_component_code_on_pythonpath(tmp_path):
    repo_root = build_repo(tmp_path / "repo")
    content = (
        "import foo_mod\n"
        "\n"
        "\n"
        "def test_x():\n"
        "    assert foo_mod.value() == 7\n"
    )
    outcome = {
        "model_call_error": None,
        "file": {"path": GOOD_PATH, "content": content},
    }
    entry, scenario = run(repo_root, outcome)
    assert field(scenario, "result") == "pass"
    assert (repo_root / GOOD_PATH).is_file()