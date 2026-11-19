# hotdocs-criterion: sha256:b0da5a97e89bde6d9051a804fb08228d14ef56e0dc2c4f2dc036c0d9bbd72905
import os
import shutil
import sys
from pathlib import Path

import capability_scenario_verifier


GHERKIN = "Given a x is 1\nThen x equals 1"
COMPILED_REL = Path("verification") / "capabilities" / "P-X" / "compiled"
TEST_FILE_NAME = "test_cs_x_001.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _plant_python_adapter(repo_root):
    src = (
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n"
    )
    _write(repo_root / "gen" / "kind-python" / "kind_python.py", src)


def _build_corpus(repo_root):
    _plant_python_adapter(repo_root)
    component_md = (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A component realizing P-X.\n"
    )
    _write(repo_root / "specs" / "components" / "foo" / "component.md", component_md)
    _write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")
    product_md = (
        "---\n"
        "id: P-X\n"
        "title: X capability\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# X capability\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        + GHERKIN + "\n"
        "```\n"
    )
    _write(repo_root / "specs" / "product" / "x.md", product_md)


def _plant_fake_compiler(repo_root, result, log_path):
    src = (
        "class ParsedCriterion:\n"
        "    def __init__(self, criterion_id=None, covers=None, kind=None, gherkin=None, file=None):\n"
        "        self.criterion_id = criterion_id\n"
        "        self.covers = covers\n"
        "        self.kind = kind\n"
        "        self.gherkin = gherkin\n"
        "        self.file = file\n"
        "\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "RESULT = " + repr(result) + "\n"
        "\n"
        "\n"
        "def compile_criterion(parsed, surface=None):\n"
        "    with open(LOG_PATH, 'a') as handle:\n"
        "        handle.write(str(parsed.criterion_id) + '\\n')\n"
        "    return dict(RESULT)\n"
    )
    _write(repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py", src)


def _scenario_result(report, scenario_id="CS-X-001"):
    cap = report["P-X"]
    scenarios = field(cap, "scenarios")
    matches = [s for s in scenarios if field(s, "id") == scenario_id]
    assert len(matches) == 1, scenarios
    return field(matches[0], "result")


def _run(repo_root):
    return capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, judge=None, test_author=None
    )


def test_compiled_true_source_is_written_run_and_passes(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "compiler.log"
    _build_corpus(repo_root)
    source = "def test_x():\n    assert True\n"
    _plant_fake_compiler(repo_root, {"status": "compiled", "source": source}, log_path)

    report = _run(repo_root)

    assert log_path.is_file()
    assert "CS-X-001" in log_path.read_text().splitlines()
    written = repo_root / COMPILED_REL / TEST_FILE_NAME
    assert written.is_file()
    assert written.read_text() == source
    assert _scenario_result(report) == "pass"


def test_compiled_false_source_is_written_and_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "compiler.log"
    _build_corpus(repo_root)
    source = "def test_x():\n    assert False\n"
    _plant_fake_compiler(repo_root, {"status": "compiled", "source": source}, log_path)

    report = _run(repo_root)

    assert log_path.is_file()
    assert "CS-X-001" in log_path.read_text().splitlines()
    written = repo_root / COMPILED_REL / TEST_FILE_NAME
    assert written.is_file()
    assert written.read_text() == source
    assert _scenario_result(report) == "fail"


def test_compile_error_fails_and_writes_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "compiler.log"
    _build_corpus(repo_root)
    _plant_fake_compiler(repo_root, {"status": "error", "message": "bad step"}, log_path)

    report = _run(repo_root)

    assert log_path.is_file()
    assert "CS-X-001" in log_path.read_text().splitlines()
    assert _scenario_result(report) == "fail"
    compiled_dir = repo_root / COMPILED_REL
    if compiled_dir.exists():
        files = [p for p in compiled_dir.rglob("*") if p.is_file()]
        assert files == []


def test_real_compiler_compiling_alone_is_not_a_pass(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    live = (
        Path(capability_scenario_verifier.__file__).resolve().parents[1]
        / "llm-endpoint"
    ).resolve().parents[1]
    live_compiler = live / "pipeline" / "criterion-compiler"
    assert live_compiler.is_dir(), live_compiler
    shutil.copytree(
        live_compiler,
        repo_root / "pipeline" / "criterion-compiler",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    report = _run(repo_root)

    result = _scenario_result(report)
    assert result == "fail"
    assert result != "pass"