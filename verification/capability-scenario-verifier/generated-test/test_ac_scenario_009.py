# hotdocs-criterion: sha256:103f87d46bbcf651df4605af937c8db4704426e5f125a30ae16d25c4aad20a35
import shutil
from pathlib import Path

import pytest

import capability_scenario_verifier


COMPILED_REL = Path("verification") / "capabilities" / "P-X" / "compiled"
COMPILED_FILE_REL = COMPILED_REL / "test_cs_x_001.py"
GHERKIN = "Given a x is 1\nThen x equals 1"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    # A non-sealed component realizing P-X, with its code under gen/foo/.
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
        "A fixture component.\n",
    )
    _write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")

    # The product capability with one compiled scenario.
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        "id: P-X\n"
        "title: X\n"
        "status: draft\n"
        "owners: [tester]\n"
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
        + GHERKIN
        + "\n```\n",
    )

    # Fake test-author and llm-endpoint, matching their documented shapes.
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
        "            'path': 'verification/capabilities/P-X/generated-test/test_cs_x_001.py',\n"
        "            'content': 'def test_x():\\n    assert True\\n',\n"
        "        },\n"
        "        'model_call_error': None,\n"
        "    }\n",
    )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {'text': 'pass', 'model': model, 'backend': 'fake', 'model_call_error': None}\n",
    )


def _write_fake_compiler(repo_root, result, log_path):
    _write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        "GATE_VERSION = 'criterion-compiler@1.0.0'\n"
        "RESULT = " + repr(result) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
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
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(str(getattr(parsed, 'criterion_id', '')) + '\\n')\n"
        "    return dict(RESULT)\n",
    )


def _scenario_result(report):
    cap = field(report, "P-X")
    scenarios = list(field(cap, "scenarios"))
    matching = [s for s in scenarios if field(s, "id") == "CS-X-001"]
    assert len(matching) == 1, scenarios
    return field(matching[0], "result")


def _run(repo_root):
    return capability_scenario_verifier.run_capability_scenarios(
        ["comp-foo"], repo_root, judge=None, test_author=None
    )


def test_compiled_passing_source_is_written_run_and_passes(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    log = tmp_path / "compiler.log"
    source = "def test_x():\n    assert True\n"
    _write_fake_compiler(repo_root, {"status": "compiled", "source": source}, log)

    report = _run(repo_root)

    assert log.is_file() and log.read_text(encoding="utf-8").strip() != ""
    written = repo_root / COMPILED_FILE_REL
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == source
    assert _scenario_result(report) == "pass"


def test_compiled_failing_source_is_written_and_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    log = tmp_path / "compiler.log"
    source = "def test_x():\n    assert False\n"
    _write_fake_compiler(repo_root, {"status": "compiled", "source": source}, log)

    report = _run(repo_root)

    written = repo_root / COMPILED_FILE_REL
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == source
    assert _scenario_result(report) == "fail"


def test_compile_error_fails_and_writes_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    log = tmp_path / "compiler.log"
    _write_fake_compiler(repo_root, {"status": "error", "message": "bad step"}, log)

    report = _run(repo_root)

    assert log.is_file() and log.read_text(encoding="utf-8").strip() != ""
    assert _scenario_result(report) == "fail"
    compiled_dir = repo_root / COMPILED_REL
    if compiled_dir.exists():
        assert [p for p in compiled_dir.rglob("*") if p.is_file()] == []


def _find_live_compiler_dir():
    here = Path(capability_scenario_verifier.__file__).resolve()
    for parent in here.parents:
        candidate = parent / "pipeline" / "criterion-compiler"
        if candidate.is_dir() and (
            (candidate / "criterion_compiler.py").is_file()
            or (candidate / "criterion_compiler" / "__init__.py").is_file()
        ):
            return candidate
    return None


def test_real_compiler_compiling_alone_is_not_a_pass(tmp_path):
    live = _find_live_compiler_dir()
    if live is None:
        pytest.skip("live repository's pipeline/criterion-compiler/ not found")

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)
    dest = repo_root / "pipeline" / "criterion-compiler"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(live, dest, ignore=shutil.ignore_patterns("__pycache__"))

    report = _run(repo_root)

    result = _scenario_result(report)
    assert result == "fail"
    assert result != "pass"