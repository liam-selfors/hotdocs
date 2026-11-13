import shutil
from pathlib import Path

import pytest

import capability_scenario_verifier


SCENARIO_ID = "CS-X-001"
CAPABILITY_ID = "P-X"
DEFAULT_TEST_PATH = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"
PASSING_TEST = "def test_x():\n    assert True\n"
FAILING_TEST = "def test_x():\n    assert False\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def capability_entry(report, capability_id):
    if isinstance(report, dict):
        return report[capability_id]
    try:
        return report[capability_id]
    except (TypeError, KeyError):
        return getattr(report, capability_id)


def scenario_entry(report, scenario_id=SCENARIO_ID):
    entry = capability_entry(report, CAPABILITY_ID)
    scenarios = field(entry, "scenarios")
    matches = [s for s in scenarios if field(s, "id") == scenario_id]
    assert len(matches) == 1, f"expected exactly one {scenario_id} entry, got {scenarios!r}"
    return matches[0]


def _tool_root():
    module_file = Path(capability_scenario_verifier.__file__).resolve()
    for parent in module_file.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repo(repo_root: Path):
    # Realizing component (unsealed), code under gen/foo/.
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [tester]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component realizing P-X.\n",
    )
    _write(
        repo_root / "gen" / "foo" / "foo_mod.py",
        "def value():\n    return 7\n",
    )

    # Product capability with one generated-test scenario.
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [tester]\n"
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
        "When value is called\n"
        "Then the result is 7\n"
        "```\n",
    )

    # Fake test-author dependency (flat module shape).
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    return {\n"
        "        'component_id': 'comp-foo',\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {\n"
        f"            'path': {DEFAULT_TEST_PATH!r},\n"
        f"            'content': {PASSING_TEST!r},\n"
        "        },\n"
        "        'model_call_error': None,\n"
        "    }\n",
    )

    # Fake llm-endpoint dependency (flat module shape).
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\n"
        "        'text': 'pass',\n"
        "        'model': model,\n"
        "        'backend': 'fake',\n"
        "        'model_call_error': None,\n"
        "    }\n",
    )

    # Copy the real criterion compiler to the same relative path.
    tool_root = _tool_root()
    if tool_root is not None:
        src = tool_root / "pipeline" / "criterion-compiler"
        if src.is_dir():
            shutil.copytree(
                src,
                repo_root / "pipeline" / "criterion-compiler",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )


def make_author(result):
    calls = []

    def test_author(bundle):
        calls.append(bundle)
        return result

    test_author.calls = calls
    return test_author


def run(repo_root, test_author):
    return capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, judge=None, test_author=test_author
    )


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    build_repo(root)
    return root


def test_failing_generated_test_fails_and_file_is_written(repo_root):
    author = make_author(
        {
            "model_call_error": None,
            "file": {"path": DEFAULT_TEST_PATH, "content": FAILING_TEST},
        }
    )
    report = run(repo_root, author)

    scenario = scenario_entry(report)
    assert field(scenario, "kind") == "generated-test"
    assert field(scenario, "result") == "fail"
    assert field(capability_entry(report, CAPABILITY_ID), "overall") == "fail"

    written = repo_root / DEFAULT_TEST_PATH
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == FAILING_TEST


@pytest.mark.parametrize("path_kind", ["dotdot", "absolute", "notverification"])
def test_disallowed_path_fails_and_nothing_written(tmp_path, repo_root, path_kind):
    if path_kind == "dotdot":
        returned_path = "../escape.py"
        target = (repo_root / "..").resolve() / "escape.py"
    elif path_kind == "absolute":
        outside = tmp_path / "separate_outside_dir"
        outside.mkdir()
        target = outside / "abs_escape.py"
        returned_path = str(target)
    else:
        returned_path = "notverification/x.py"
        target = repo_root / "notverification" / "x.py"

    assert not target.exists()

    author = make_author(
        {
            "model_call_error": None,
            "file": {"path": returned_path, "content": PASSING_TEST},
        }
    )
    report = run(repo_root, author)

    scenario = scenario_entry(report)
    assert field(scenario, "result") == "fail"
    assert not target.exists(), f"something was written at {target}"


@pytest.mark.parametrize(
    "result",
    [
        {
            "model_call_error": {"category": "network", "message": "fake failure"},
            "file": None,
        },
        {"model_call_error": None, "file": None},
    ],
    ids=["model_call_error", "no_file"],
)
def test_model_call_error_or_no_file_fails(repo_root, result):
    author = make_author(result)
    report = run(repo_root, author)

    scenario = scenario_entry(report)
    assert field(scenario, "result") == "fail"


def test_test_runs_with_realizing_component_code_on_pythonpath(repo_root):
    content = (
        "import foo_mod\n"
        "\n"
        "\n"
        "def test_x():\n"
        "    assert foo_mod.value() == 7\n"
    )
    author = make_author(
        {
            "model_call_error": None,
            "file": {"path": DEFAULT_TEST_PATH, "content": content},
        }
    )
    report = run(repo_root, author)

    scenario = scenario_entry(report)
    assert field(scenario, "result") == "pass"
    assert (repo_root / DEFAULT_TEST_PATH).is_file()