# hotdocs-criterion: sha256:57197751e6132f80e5b53316a7a72c6d7d3ccffc43ec87b452391d35d7c8ae2f
import shutil
import sys
from pathlib import Path

import pytest

import capability_scenario_verifier


SCENARIO_ID = "CS-X-001"
CAP_ID = "P-X"
GHERKIN = "Given a x is 1\nThen x equals 1"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_corpus(repo_root, kind="compiled", gherkin=GHERKIN):
    # python kind adapter, so no criterion depends on the tool's own
    write(
        repo_root / "gen" / "kind-python" / "kind_python.py",
        "import sys\n"
        "\n"
        "\n"
        "def provision(repo_root):\n"
        "    return {\"ok\": True, \"reason\": \"\", \"versions\": {}, \"lockfile_sha256\": None,\n"
        "            \"interpreter\": sys.executable}\n",
    )

    # a realizing, non-sealed component with its code under gen/x/
    write(
        repo_root / "specs" / "components" / "x" / "component.md",
        "---\n"
        "id: comp-x\n"
        "title: X\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "realizes: [P-X]\n"
        "sealed: false\n"
        "---\n"
        "\n"
        "# X\n"
        "\n"
        "A fixture component.\n",
    )
    write(repo_root / "gen" / "x" / "x.py", "def value():\n    return 1\n")

    # the capability with one scenario
    write(
        repo_root / "specs" / "product" / "x.md",
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
        "Kind: " + kind + "\n"
        "\n"
        "```gherkin\n"
        + gherkin + "\n"
        "```\n",
    )

    # small fakes for test-author and llm-endpoint
    write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    return {\n"
        "        \"component_id\": \"comp-x\",\n"
        "        \"criterion_id\": bundle[\"criterion_id\"],\n"
        "        \"model\": model,\n"
        "        \"seed\": seed,\n"
        "        \"prompt_version\": \"v1\",\n"
        "        \"cache_hit\": False,\n"
        "        \"file\": {\"path\": "
        + repr("verification/capabilities/P-X/generated-test/test_cs_x_001.py")
        + ", \"content\": " + repr("def test_x():\n    assert True\n") + "},\n"
        "        \"model_call_error\": None,\n"
        "        \"repair_attempts\": 0,\n"
        "        \"probe_findings\": [],\n"
        "    }\n",
    )
    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\"text\": \"pass\", \"model\": model, \"backend\": \"fake\",\n"
        "            \"model_call_error\": None}\n",
    )


def write_fake_compiler(repo_root, result, log_path):
    write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        "GATE_VERSION = \"criterion-compiler@1.0.0\"\n"
        "\n"
        "\n"
        "class ParsedCriterion:\n"
        "    def __init__(self, criterion_id=None, covers=None, kind=None, gherkin=None, file=None):\n"
        "        self.criterion_id = criterion_id\n"
        "        self.covers = covers\n"
        "        self.kind = kind\n"
        "        self.gherkin = gherkin\n"
        "        self.file = file\n"
        "\n"
        "\n"
        "def compile_criterion(parsed, surface=None):\n"
        "    with open(" + repr(str(log_path)) + ", \"a\") as fh:\n"
        "        fh.write(\"called\\n\")\n"
        "    return dict(" + repr(result) + ")\n",
    )


def scenario_result(report):
    cap = field(report, CAP_ID)
    scenarios = field(cap, "scenarios")
    matching = [s for s in scenarios if field(s, "id") == SCENARIO_ID]
    assert len(matching) == 1, scenarios
    return field(matching[0], "result")


def compiled_path(repo_root):
    return (repo_root / "verification" / "capabilities" / "P-X" / "compiled"
            / "test_cs_x_001.py")


@pytest.mark.parametrize(
    "source, expected",
    [
        ("def test_x():\n    assert True\n", "pass"),
        ("def test_x():\n    assert False\n", "fail"),
    ],
)
def test_compiled_source_is_written_and_run(tmp_path, source, expected):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)
    log_path = tmp_path / "compile.log"
    write_fake_compiler(repo_root, {"status": "compiled", "source": source}, log_path)

    report = capability_scenario_verifier.run_capability_scenarios(["comp-x"], repo_root)

    assert log_path.is_file(), "fake compile_criterion was never called"
    path = compiled_path(repo_root)
    assert path.is_file()
    assert path.read_text() == source
    assert scenario_result(report) == expected


def test_compile_error_is_fail_with_nothing_written(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root)
    log_path = tmp_path / "compile.log"
    write_fake_compiler(repo_root, {"status": "error", "message": "bad step"}, log_path)

    report = capability_scenario_verifier.run_capability_scenarios(["comp-x"], repo_root)

    assert log_path.is_file(), "fake compile_criterion was never called"
    assert scenario_result(report) == "fail"
    compiled_dir = repo_root / "verification" / "capabilities" / "P-X" / "compiled"
    if compiled_dir.exists():
        assert [p for p in compiled_dir.rglob("*") if p.is_file()] == []


def test_real_compiler_compiling_alone_is_not_a_pass(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_corpus(repo_root, gherkin=GHERKIN)

    live = (Path(capability_scenario_verifier.__file__).resolve().parents[1]
            / "llm-endpoint").resolve().parents[1]
    src = live / "pipeline" / "criterion-compiler"
    shutil.copytree(
        src,
        repo_root / "pipeline" / "criterion-compiler",
        ignore=shutil.ignore_patterns("__pycache__"),
    )

    report = capability_scenario_verifier.run_capability_scenarios(["comp-x"], repo_root)

    result = scenario_result(report)
    assert result != "pass"
    assert result == "fail"