# hotdocs-criterion: sha256:4c6f2ca3b8c831fbd00205fd01fd737cf0369582cca9232d95b7b2a9d401527d
import shutil
import sys
from pathlib import Path

import pytest

import capability_scenario_verifier


PASS_SOURCE = "def test_x():\n    assert True\n"
FAIL_SOURCE = "def test_x():\n    assert False\n"
GHERKIN = "Given a x is 1\nThen x equals 1"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture(autouse=True)
def _forget_cached_compiler():
    # Each test supplies its own criterion_compiler under its own repo_root;
    # make sure a module loaded by an earlier test is not reused by name.
    sys.modules.pop("criterion_compiler", None)
    yield
    sys.modules.pop("criterion_compiler", None)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    _write(
        repo / "specs" / "components" / "x" / "component.md",
        "---\n"
        "id: comp-x\n"
        "title: X\n"
        "status: draft\n"
        "owners: [team]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# X\n"
        "\n"
        "A component realizing capability P-X.\n",
    )
    _write(repo / "gen" / "x" / "x.py", "VALUE = 1\n")

    _write(
        repo / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: Capability X\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Capability X\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        + GHERKIN
        + "\n"
        "```\n",
    )

    # Small fakes for the other dependencies, per the fixture rules.
    _write(
        repo / "gen" / "test-author" / "test_author.py",
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    return {\n"
        "        'component_id': 'comp-x',\n"
        "        'criterion_id': bundle['criterion_id'],\n"
        "        'model': model,\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': {\n"
        "            'path': 'verification/capabilities/P-X/generated-test/test_cs_x_001.py',\n"
        "            'content': " + repr(PASS_SOURCE) + ",\n"
        "        },\n"
        "        'model_call_error': None,\n"
        "    }\n",
    )
    _write(
        repo / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\n"
        "        'text': 'pass',\n"
        "        'model': model,\n"
        "        'backend': 'fake',\n"
        "        'model_call_error': None,\n"
        "    }\n",
    )
    return repo


def write_fake_compiler(repo, result, log_path):
    _write(
        repo / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        "class ParsedCriterion:\n"
        "    def __init__(self, criterion_id=None, covers=None, kind=None, gherkin=None, file=None):\n"
        "        self.criterion_id = criterion_id\n"
        "        self.covers = covers\n"
        "        self.kind = kind\n"
        "        self.gherkin = gherkin\n"
        "        self.file = file\n"
        "\n"
        "\n"
        "RESULT = " + repr(result) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def compile_criterion(parsed, surface=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(str(getattr(parsed, 'criterion_id', '')) + '\\n')\n"
        "    return dict(RESULT)\n",
    )


def copy_real_compiler(repo):
    live = (
        Path(capability_scenario_verifier.__file__).resolve().parents[1] / "llm-endpoint"
    ).resolve().parents[1]
    src = live / "pipeline" / "criterion-compiler"
    dst = repo / "pipeline" / "criterion-compiler"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))


def scenario_result(report, scenario_id):
    entry = field(report, "P-X")
    scenarios = field(entry, "scenarios")
    matches = [s for s in scenarios if field(s, "id") == scenario_id]
    assert len(matches) == 1, scenarios
    return field(matches[0], "result")


def compiled_dir(repo):
    return repo / "verification" / "capabilities" / "P-X" / "compiled"


def test_compiled_source_passing_is_written_run_and_passes(tmp_path):
    repo = make_repo(tmp_path)
    log = tmp_path / "compile.log"
    write_fake_compiler(repo, {"status": "compiled", "source": PASS_SOURCE}, log)

    report = capability_scenario_verifier.run_capability_scenarios(["comp-x"], repo)

    written = compiled_dir(repo) / "test_cs_x_001.py"
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == PASS_SOURCE
    assert log.is_file() and log.read_text(encoding="utf-8").strip() != ""
    assert scenario_result(report, "CS-X-001") == "pass"


def test_compiled_source_failing_is_written_and_fails(tmp_path):
    repo = make_repo(tmp_path)
    log = tmp_path / "compile.log"
    write_fake_compiler(repo, {"status": "compiled", "source": FAIL_SOURCE}, log)

    report = capability_scenario_verifier.run_capability_scenarios(["comp-x"], repo)

    written = compiled_dir(repo) / "test_cs_x_001.py"
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == FAIL_SOURCE
    assert scenario_result(report, "CS-X-001") == "fail"


def test_compile_error_fails_and_writes_nothing(tmp_path):
    repo = make_repo(tmp_path)
    log = tmp_path / "compile.log"
    write_fake_compiler(repo, {"status": "error", "message": "bad step"}, log)

    report = capability_scenario_verifier.run_capability_scenarios(["comp-x"], repo)

    assert scenario_result(report, "CS-X-001") == "fail"
    d = compiled_dir(repo)
    existing = [p for p in d.rglob("*") if p.is_file()] if d.exists() else []
    assert existing == []


def test_real_compiler_compiling_alone_is_not_a_pass(tmp_path):
    repo = make_repo(tmp_path)
    copy_real_compiler(repo)

    report = capability_scenario_verifier.run_capability_scenarios(["comp-x"], repo)

    result = scenario_result(report, "CS-X-001")
    assert result != "pass"
    assert result == "fail"