# hotdocs-criterion: sha256:3ac1ee4770bf3f8394cc4e56659b1a00cd5125cf671ad5bf5cdcc8caafac9159
import shutil
import sys
from pathlib import Path

import capability_scenario_verifier


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


GHERKIN = "Given a x is 1\nThen x equals 1"


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_repo(repo_root):
    repo_root = Path(repo_root)
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )
    write(
        repo_root / "specs" / "components" / "foo" / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [a]\n"
        "depends_on: []\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# Foo\n",
    )
    write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")
    write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: X\n"
        "status: draft\n"
        "owners: [a]\n"
        "---\n"
        "\n"
        "# X\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        + GHERKIN + "\n"
        "```\n",
    )
    return repo_root


def plant_fake_compiler(repo_root, result):
    write(
        Path(repo_root) / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
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
        "\n"
        "\n"
        "def compile_criterion(parsed, surface=None):\n"
        "    return dict(RESULT)\n",
    )


def scenario_result(report):
    entry = field(report, "P-X") if not isinstance(report, dict) else report["P-X"]
    scenarios = field(entry, "scenarios")
    matching = [s for s in scenarios if field(s, "id") == "CS-X-001"]
    assert len(matching) == 1, scenarios
    return field(matching[0], "result")


def run(repo_root):
    return capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo", "foo"], Path(repo_root)
    )


def compiled_dir(repo_root):
    return Path(repo_root) / "verification" / "capabilities" / "P-X" / "compiled"


def test_compiled_source_written_run_and_passes(tmp_path):
    repo_root = build_repo(tmp_path / "repo")
    source = "def test_x():\n    assert True\n"
    plant_fake_compiler(repo_root, {"status": "compiled", "source": source})

    report = run(repo_root)

    target = compiled_dir(repo_root) / "test_cs_x_001.py"
    assert target.is_file()
    assert target.read_text(encoding="utf-8") == source
    assert scenario_result(report) == "pass"


def test_compiled_failing_source_written_and_fails(tmp_path):
    repo_root = build_repo(tmp_path / "repo")
    source = "def test_x():\n    assert False\n"
    plant_fake_compiler(repo_root, {"status": "compiled", "source": source})

    report = run(repo_root)

    target = compiled_dir(repo_root) / "test_cs_x_001.py"
    assert target.is_file()
    assert scenario_result(report) == "fail"


def test_compile_error_fails_and_writes_nothing(tmp_path):
    repo_root = build_repo(tmp_path / "repo")
    plant_fake_compiler(repo_root, {"status": "error", "message": "bad step"})

    report = run(repo_root)

    assert scenario_result(report) == "fail"
    out = compiled_dir(repo_root)
    if out.exists():
        files = [p for p in out.rglob("*") if p.is_file()]
        assert files == []


def test_real_compiler_compiling_alone_is_not_a_pass(tmp_path):
    repo_root = build_repo(tmp_path / "repo")
    live = (
        Path(capability_scenario_verifier.__file__).resolve().parents[1]
        / "llm-endpoint"
    ).resolve().parents[1]
    src = live / "pipeline" / "criterion-compiler"
    dst = repo_root / "pipeline" / "criterion-compiler"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))

    report = run(repo_root)

    result = scenario_result(report)
    assert result == "fail"
    assert result != "pass"