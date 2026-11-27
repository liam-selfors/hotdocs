# hotdocs-criterion: sha256:df91c69c6b06f978603dcdb576bc5657b5c5666f8ca2299edce5d68df1824196
import os
from pathlib import Path

import pytest

import capability_scenario_verifier


SCENARIO_ID = "CS-X-001"
CAPABILITY_ID = "P-X"
GOOD_PATH = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"


def field(value, name):
    if isinstance(value, dict):
        return value[name]
    try:
        return getattr(value, name)
    except AttributeError:
        return value[name]


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


KIND_PYTHON_SRC = (
    "import sys\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
    "            \"interpreter\": sys.executable}\n"
)

FAKE_TEST_AUTHOR_SRC = (
    "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
    "    return {\n"
    "        \"component_id\": \"comp-foo\",\n"
    "        \"criterion_id\": bundle[\"criterion_id\"],\n"
    "        \"model\": model,\n"
    "        \"seed\": seed,\n"
    "        \"prompt_version\": \"v1\",\n"
    "        \"cache_hit\": False,\n"
    "        \"file\": {\"path\": " + repr(GOOD_PATH) + ",\n"
    "                 \"content\": \"def test_x():\\n    assert True\\n\"},\n"
    "        \"model_call_error\": None,\n"
    "        \"repair_attempts\": 0,\n"
    "        \"probe_findings\": [],\n"
    "    }\n"
)

FAKE_LLM_ENDPOINT_SRC = (
    "def complete(prompt, model, *, backend=None, **params):\n"
    "    return {\"text\": \"PASS\", \"model\": model, \"backend\": \"fake\",\n"
    "            \"model_call_error\": None}\n"
)

COMPONENT_MD = (
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
    "# Foo\n"
    "\n"
    "A fixture component.\n"
)

PRODUCT_MD = (
    "---\n"
    "id: P-X\n"
    "title: Capability X\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
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
    "When the capability is exercised\n"
    "Then it works\n"
    "```\n"
)

FOO_MOD_SRC = (
    "def value():\n"
    "    return 7\n"
)


def build_repo(repo_root):
    repo_root.mkdir(parents=True, exist_ok=True)
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", KIND_PYTHON_SRC)
    _write(repo_root / "gen" / "test-author" / "test_author.py", FAKE_TEST_AUTHOR_SRC)
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", FAKE_LLM_ENDPOINT_SRC)
    _write(repo_root / "specs" / "components" / "foo" / "component.md", COMPONENT_MD)
    _write(repo_root / "gen" / "foo" / "foo_mod.py", FOO_MOD_SRC)
    _write(repo_root / "specs" / "product" / "x.md", PRODUCT_MD)
    return repo_root


def make_author(result):
    def test_author(bundle):
        return result
    return test_author


def file_author(path, content):
    return make_author({"model_call_error": None,
                        "file": {"path": path, "content": content}})


def run(repo_root, test_author):
    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, judge=None, test_author=test_author)
    cap = field(report, CAPABILITY_ID)
    scenarios = list(field(cap, "scenarios"))
    matching = [s for s in scenarios if field(s, "id") == SCENARIO_ID]
    assert len(matching) == 1, scenarios
    return cap, matching[0]


def test_failing_generated_test_fails_and_is_written(tmp_path):
    repo_root = build_repo(tmp_path / "repo")
    content = "def test_x():\n    assert False\n"
    cap, scenario = run(repo_root, file_author(GOOD_PATH, content))
    assert field(scenario, "result") == "fail"
    assert field(cap, "overall") == "fail"
    written = repo_root / GOOD_PATH
    assert written.is_file()
    assert written.read_text() == content


@pytest.mark.parametrize("which", ["dotdot", "absolute", "notverification"])
def test_invalid_returned_path_fails_and_writes_nothing(tmp_path, tmp_path_factory, which):
    repo_root = build_repo(tmp_path / "repo")
    if which == "dotdot":
        returned = "../escape.py"
        target = (repo_root / returned).resolve()
    elif which == "absolute":
        outside = tmp_path_factory.mktemp("outside")
        target = outside / "escape.py"
        returned = str(target)
    else:
        returned = "notverification/x.py"
        target = repo_root / returned
    assert not target.exists()
    cap, scenario = run(repo_root, file_author(returned, "def test_x():\n    assert True\n"))
    assert field(scenario, "result") == "fail"
    assert field(cap, "overall") == "fail"
    assert not target.exists()
    assert not os.path.lexists(str(target))


@pytest.mark.parametrize("outcome", [
    {"model_call_error": {"category": "network", "message": "connection failed"}, "file": None},
    {"model_call_error": None, "file": None},
])
def test_model_call_error_or_no_file_fails(tmp_path, outcome):
    repo_root = build_repo(tmp_path / "repo")
    cap, scenario = run(repo_root, make_author(outcome))
    assert field(scenario, "result") == "fail"
    assert field(cap, "overall") == "fail"


def test_realizing_component_code_dir_on_pythonpath(tmp_path):
    repo_root = build_repo(tmp_path / "repo")
    content = (
        "import foo_mod\n"
        "\n"
        "\n"
        "def test_x():\n"
        "    assert foo_mod.value() == 7\n"
    )
    cap, scenario = run(repo_root, file_author(GOOD_PATH, content))
    assert field(scenario, "result") == "pass"
    assert field(cap, "overall") == "pass"
    assert (repo_root / GOOD_PATH).is_file()