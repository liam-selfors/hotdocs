# hotdocs-criterion: sha256:d5937dffd19624d0a68f1763506c1d37b7ce12907fe1e2ae0bcbeeaba3bbfaee
import shutil
from pathlib import Path

import pytest

import capability_scenario_verifier


SCENARIO_ID = "CS-X-001"
CAPABILITY_ID = "P-X"
GOOD_PATH = "verification/capabilities/P-X/generated-test/test_cs_x_001.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _live_repo_root():
    for p in Path(capability_scenario_verifier.__file__).resolve().parents:
        if p.name == "gen":
            return p.parent
    return None


FAKE_TEST_AUTHOR_SRC = (
    "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
    "    cid = bundle['criterion_id']\n"
    "    name = 'test_' + cid.lower().replace('-', '_') + '.py'\n"
    "    return {\n"
    "        'component_id': bundle.get('component_id'),\n"
    "        'criterion_id': cid,\n"
    "        'model': model,\n"
    "        'seed': seed,\n"
    "        'prompt_version': 'v1',\n"
    "        'cache_hit': False,\n"
    "        'file': {\n"
    "            'path': 'verification/capabilities/P-X/generated-test/' + name,\n"
    "            'content': " + repr("def test_x():\n    assert True\n") + ",\n"
    "        },\n"
    "        'model_call_error': None,\n"
    "    }\n"
)

FAKE_LLM_ENDPOINT_SRC = (
    "def complete(prompt, model, *, backend=None, **params):\n"
    "    return {'text': 'pass', 'model': model, 'backend': 'fake', 'model_call_error': None}\n"
)


def make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Component realizing P-X, unsealed, with code under gen/foo/
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A small fixture component.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "**R-FOO-001** — `value()` MUST return 7.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given nothing\n"
        "When value is called\n"
        "Then it returns 7\n"
        "```\n",
    )
    _write(
        repo_root / "gen" / "foo" / "foo_mod.py",
        "def value():\n    return 7\n",
    )

    # Capability with one generated-test scenario
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [alice]\n"
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
        "Then it returns 7\n"
        "```\n",
    )

    # Fake dependencies, flat-module shape
    _write(repo_root / "gen" / "test-author" / "test_author.py", FAKE_TEST_AUTHOR_SRC)
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", FAKE_LLM_ENDPOINT_SRC)

    # Real compiler copied from the live repository
    live = _live_repo_root()
    if live is not None:
        src = live / "pipeline" / "criterion-compiler"
        if src.is_dir():
            shutil.copytree(
                src,
                repo_root / "pipeline" / "criterion-compiler",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
    return repo_root


def make_author(outcome, calls):
    def test_author(bundle):
        calls.append(bundle)
        return outcome
    return test_author


def run(repo_root, outcome):
    calls = []
    report = capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, judge=None, test_author=make_author(outcome, calls)
    )
    return report, calls


def capability_entry(report):
    if isinstance(report, dict):
        assert CAPABILITY_ID in report, report
        return report[CAPABILITY_ID]
    return report[CAPABILITY_ID]


def scenario_result(report):
    entry = capability_entry(report)
    scenarios = field(entry, "scenarios")
    matches = [s for s in scenarios if field(s, "id") == SCENARIO_ID]
    assert len(matches) == 1, scenarios
    return field(matches[0], "result")


def test_failing_generated_test_fails_and_is_written(tmp_path):
    repo_root = make_repo(tmp_path)
    content = "def test_x():\n    assert False\n"
    outcome = {"model_call_error": None, "file": {"path": GOOD_PATH, "content": content}}

    report, calls = run(repo_root, outcome)

    assert len(calls) >= 1
    assert scenario_result(report) == "fail"
    assert field(capability_entry(report), "overall") == "fail"
    written = repo_root / GOOD_PATH
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == content


@pytest.mark.parametrize("kind", ["dotdot", "absolute", "notverification"])
def test_bad_path_fails_and_writes_nothing(tmp_path, tmp_path_factory, kind):
    repo_root = make_repo(tmp_path)
    if kind == "dotdot":
        returned = "../escape.py"
        target = (repo_root / ".." / "escape.py").resolve()
    elif kind == "absolute":
        other = tmp_path_factory.mktemp("separate_escape_dir")
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

    report, _calls = run(repo_root, outcome)

    assert scenario_result(report) == "fail"
    assert not target.exists()


@pytest.mark.parametrize(
    "outcome",
    [
        {"model_call_error": {"category": "network", "message": "connection failed"}, "file": None},
        {"model_call_error": None, "file": None},
    ],
    ids=["model_call_error", "no_file"],
)
def test_model_error_or_no_file_fails(tmp_path, outcome):
    repo_root = make_repo(tmp_path)

    report, _calls = run(repo_root, outcome)

    assert scenario_result(report) == "fail"


def test_passing_test_runs_with_component_code_on_pythonpath(tmp_path):
    repo_root = make_repo(tmp_path)
    content = (
        "import foo_mod\n"
        "\n"
        "\n"
        "def test_x():\n"
        "    assert foo_mod.value() == 7\n"
    )
    outcome = {"model_call_error": None, "file": {"path": GOOD_PATH, "content": content}}

    report, _calls = run(repo_root, outcome)

    assert scenario_result(report) == "pass"
    assert (repo_root / GOOD_PATH).is_file()