import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

import capability_scenario_verifier


P_ID = "P-X"
SCENARIO_ID = "CS-X-001"
COMPONENT_SLUG = "foo"
COMPONENT_ID = "comp-foo"
GHERKIN = "Given a x is 1\nThen x equals 1"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _capability_entry(report, pid):
    if isinstance(report, dict):
        return report[pid]
    try:
        return report[pid]
    except (TypeError, KeyError):
        return getattr(report, pid)


def _scenario_result(report, scenario_id):
    entry = _capability_entry(report, P_ID)
    scenarios = list(_field(entry, "scenarios"))
    matches = [s for s in scenarios if _field(s, "id") == scenario_id]
    assert len(matches) == 1, f"expected exactly one {scenario_id} entry, got {scenarios!r}"
    return _field(matches[0], "result")


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _compiled_dir(repo_root):
    return repo_root / "verification" / "capabilities" / P_ID / "compiled"


def _compiled_file(repo_root):
    return _compiled_dir(repo_root) / "test_cs_x_001.py"


def _build_repo(repo_root):
    # A non-sealed component realizing P-X, with its code under gen/foo/.
    _write(
        repo_root / "specs" / "components" / COMPONENT_SLUG / "component.md",
        "---\n"
        f"id: {COMPONENT_ID}\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [tester]\n"
        f"realizes: [{P_ID}]\n"
        "sealed: false\n"
        "---\n\n"
        "# Foo\n\nA fixture component.\n",
    )
    _write(repo_root / "gen" / COMPONENT_SLUG / "foo.py", "VALUE = 1\n")

    # The capability, under specs/product/.
    _write(
        repo_root / "specs" / "product" / "x.md",
        "---\n"
        f"id: {P_ID}\n"
        "title: X capability\n"
        "status: draft\n"
        "owners: [tester]\n"
        "---\n\n"
        "# X capability\n\n"
        f"### {SCENARIO_ID}\n\n"
        f"Covers: {P_ID}\n"
        "Kind: compiled\n\n"
        "```gherkin\n"
        f"{GHERKIN}\n"
        "```\n",
    )

    # Small fakes for the other two dependencies (unused by compiled scenarios).
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    return {\n"
        "        \"component_id\": None,\n"
        "        \"criterion_id\": bundle[\"criterion_id\"],\n"
        "        \"model\": model,\n"
        "        \"seed\": seed,\n"
        "        \"prompt_version\": \"v1\",\n"
        "        \"cache_hit\": False,\n"
        "        \"file\": {\n"
        "            \"path\": \"verification/capabilities/P-X/generated-test/test_cs_x_001.py\",\n"
        "            \"content\": \"def test_x():\\n    assert True\\n\",\n"
        "        },\n"
        "        \"model_call_error\": None,\n"
        "    }\n",
    )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(prompt, model, *, backend=None, **params):\n"
        "    return {\"text\": \"pass\", \"model\": model, \"backend\": \"fake\", \"model_call_error\": None}\n",
    )


def _write_fake_compiler(repo_root, result, log_path):
    source = (
        "import json\n"
        "from dataclasses import dataclass\n"
        "\n"
        f"_RESULT = json.loads({json.dumps(json.dumps(result))})\n"
        f"_LOG = {str(log_path)!r}\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class ParsedCriterion:\n"
        "    criterion_id: str = None\n"
        "    covers: str = None\n"
        "    kind: str = None\n"
        "    gherkin: str = None\n"
        "    file: str = None\n"
        "\n"
        "\n"
        "def compile_criterion(parsed, surface=None):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'criterion_id': getattr(parsed, 'criterion_id', None)}) + '\\n')\n"
        "    return dict(_RESULT)\n"
    )
    _write(repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py", source)


def _log_entries(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _tool_root():
    here = Path(capability_scenario_verifier.__file__).resolve()
    for parent in here.parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _real_compiler_dir():
    candidates = []
    tr = _tool_root()
    if tr is not None:
        candidates.append(tr)
    candidates.extend(Path(capability_scenario_verifier.__file__).resolve().parents)
    for base in candidates:
        d = base / "pipeline" / "criterion-compiler"
        if (d / "criterion_compiler.py").is_file() or (d / "criterion_compiler" / "__init__.py").is_file():
            return d
    return None


def _load_from_path(module_name, path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _isolate_modules(monkeypatch):
    for name in ("criterion_compiler", "test_author", "llm_endpoint"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    yield


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_compiled_passing_source_is_written_run_and_passes(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    source = "def test_x():\n    assert True\n"
    log_path = tmp_path / "compile_log.jsonl"
    _write_fake_compiler(repo_root, {"status": "compiled", "source": source}, log_path)

    report = capability_scenario_verifier.run_capability_scenarios([COMPONENT_ID], repo_root)

    assert [e["criterion_id"] for e in _log_entries(log_path)] == [SCENARIO_ID]
    out = _compiled_file(repo_root)
    assert out.is_file(), f"expected compiled test at {out}"
    assert out.read_text(encoding="utf-8") == source
    assert _scenario_result(report, SCENARIO_ID) == "pass"


def test_compiled_failing_source_is_written_and_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    source = "def test_x():\n    assert False\n"
    log_path = tmp_path / "compile_log.jsonl"
    _write_fake_compiler(repo_root, {"status": "compiled", "source": source}, log_path)

    report = capability_scenario_verifier.run_capability_scenarios([COMPONENT_ID], repo_root)

    assert [e["criterion_id"] for e in _log_entries(log_path)] == [SCENARIO_ID]
    out = _compiled_file(repo_root)
    assert out.is_file(), f"expected compiled test at {out}"
    assert out.read_text(encoding="utf-8") == source
    assert _scenario_result(report, SCENARIO_ID) == "fail"


def test_compile_error_fails_and_writes_nothing(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    log_path = tmp_path / "compile_log.jsonl"
    _write_fake_compiler(repo_root, {"status": "error", "message": "bad step"}, log_path)

    report = capability_scenario_verifier.run_capability_scenarios([COMPONENT_ID], repo_root)

    assert [e["criterion_id"] for e in _log_entries(log_path)] == [SCENARIO_ID]
    assert _scenario_result(report, SCENARIO_ID) == "fail"
    compiled_dir = _compiled_dir(repo_root)
    if compiled_dir.exists():
        leftovers = [p for p in compiled_dir.rglob("*") if p.is_file()]
        assert leftovers == [], f"expected no files under {compiled_dir}, found {leftovers}"


def test_real_compiler_output_that_compiles_but_fails_is_not_a_pass(tmp_path):
    real_dir = _real_compiler_dir()
    assert real_dir is not None, "could not locate the live repository's pipeline/criterion-compiler/"

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_repo(repo_root)
    dest = repo_root / "pipeline" / "criterion-compiler"
    shutil.copytree(real_dir, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    # Precondition: the copied real compiler does compile this gherkin.
    flat = dest / "criterion_compiler.py"
    path = flat if flat.is_file() else dest / "criterion_compiler" / "__init__.py"
    module_name = "_ac_scenario_009_real_criterion_compiler"
    try:
        real_cc = _load_from_path(module_name, path)
        parsed = real_cc.ParsedCriterion(
            criterion_id=SCENARIO_ID,
            covers=P_ID,
            kind="compiled",
            gherkin=GHERKIN,
            file="specs/product/x.md",
        )
        compiled = real_cc.compile_criterion(parsed, surface=None)
        assert _field(compiled, "status") == "compiled", f"precondition: expected compiled, got {compiled!r}"
    finally:
        sys.modules.pop(module_name, None)

    report = capability_scenario_verifier.run_capability_scenarios([COMPONENT_ID], repo_root)

    result = _scenario_result(report, SCENARIO_ID)
    assert result != "pass"
    assert result == "fail"