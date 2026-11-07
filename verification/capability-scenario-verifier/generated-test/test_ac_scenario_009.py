import shutil
from pathlib import Path

import capability_scenario_verifier as csv_mod


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_component_and_capability(repo_root: Path, gherkin: str, kind: str = "compiled") -> None:
    component_dir = repo_root / "specs" / "components" / "widget"
    component_dir.mkdir(parents=True, exist_ok=True)
    (component_dir / "component.md").write_text(
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [lselfors@gmail.com]\n"
        "realizes: [P-X]\n"
        "sealed: true\n"
        "source_path: pipeline/widget/\n"
        "---\n"
    )

    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True, exist_ok=True)
    (product_dir / "widget.md").write_text(
        "---\n"
        "id: P-X\n"
        "title: Widget Capability\n"
        "status: draft\n"
        "owners: [lselfors@gmail.com]\n"
        "---\n"
        "\n"
        "### CS-X-001\n"
        "\n"
        "Covers: P-X\n"
        f"Kind: {kind}\n"
        "\n"
        "```gherkin\n"
        f"{gherkin}\n"
        "```\n"
    )


def _write_fake_compile_criterion(repo_root: Path, result: dict) -> None:
    compiler_dir = repo_root / "pipeline" / "criterion-compiler"
    compiler_dir.mkdir(parents=True, exist_ok=True)
    (compiler_dir / "criterion_compiler.py").write_text(
        "class ParsedCriterion:\n"
        "    def __init__(self, *, criterion_id, covers, kind, gherkin, file):\n"
        "        self.criterion_id = criterion_id\n"
        "        self.covers = covers\n"
        "        self.kind = kind\n"
        "        self.gherkin = gherkin\n"
        "        self.file = file\n"
        "\n"
        "\n"
        f"def compile_criterion(parsed, surface=None):\n"
        f"    return {result!r}\n"
    )


def _find_real_pipeline_compiler_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in (here.parent, *here.parents):
        candidate = parent / "pipeline" / "criterion-compiler"
        if (candidate / "criterion_compiler.py").exists():
            return candidate
    raise RuntimeError(
        "could not locate the live repository's pipeline/criterion-compiler/ "
        "directory by walking up from this test file"
    )


def _copy_real_compile_criterion(repo_root: Path) -> None:
    real_dir = _find_real_pipeline_compiler_dir()
    dest_dir = repo_root / "pipeline" / "criterion-compiler"
    dest_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(real_dir, dest_dir)


def test_compiled_scenario_passes_when_its_written_test_passes(tmp_path):
    repo_root = tmp_path
    _write_component_and_capability(
        repo_root, "Given a widget\nWhen it is assembled\nThen it is complete"
    )
    _write_fake_compile_criterion(
        repo_root,
        {"status": "compiled", "source": "def test_x():\n    assert True\n"},
    )

    report = csv_mod.run_capability_scenarios(["comp-widget"], repo_root)

    capability = _get(report, "P-X")
    scenarios = _get(capability, "scenarios")
    scenario = scenarios[0]
    assert _get(scenario, "id") == "CS-X-001"
    assert _get(scenario, "result") == "pass"

    compiled_file = (
        repo_root / "verification" / "capabilities" / "P-X" / "compiled" / "test_cs_x_001.py"
    )
    assert compiled_file.exists()
    assert compiled_file.read_text() == "def test_x():\n    assert True\n"


def test_compiled_scenario_fails_when_its_written_test_fails(tmp_path):
    repo_root = tmp_path
    _write_component_and_capability(
        repo_root, "Given a widget\nWhen it is assembled\nThen it is complete"
    )
    _write_fake_compile_criterion(
        repo_root,
        {"status": "compiled", "source": "def test_x():\n    assert False\n"},
    )

    report = csv_mod.run_capability_scenarios(["comp-widget"], repo_root)

    capability = _get(report, "P-X")
    scenario = _get(capability, "scenarios")[0]
    assert _get(scenario, "result") == "fail"

    compiled_file = (
        repo_root / "verification" / "capabilities" / "P-X" / "compiled" / "test_cs_x_001.py"
    )
    assert compiled_file.exists()


def test_compile_error_fails_with_nothing_written(tmp_path):
    repo_root = tmp_path
    _write_component_and_capability(
        repo_root, "Given a widget\nWhen it is assembled\nThen it is complete"
    )
    _write_fake_compile_criterion(
        repo_root,
        {"status": "error", "message": "bad step"},
    )

    report = csv_mod.run_capability_scenarios(["comp-widget"], repo_root)

    capability = _get(report, "P-X")
    scenario = _get(capability, "scenarios")[0]
    assert _get(scenario, "result") == "fail"

    compiled_dir = repo_root / "verification" / "capabilities" / "P-X" / "compiled"
    assert not (compiled_dir / "test_cs_x_001.py").exists()


def test_real_compiler_compiling_is_not_itself_a_pass(tmp_path):
    repo_root = tmp_path
    _write_component_and_capability(repo_root, "Given a x is 1\nThen x equals 1")
    _copy_real_compile_criterion(repo_root)

    report = csv_mod.run_capability_scenarios(["comp-widget"], repo_root)

    capability = _get(report, "P-X")
    scenario = _get(capability, "scenarios")[0]
    assert _get(scenario, "result") == "fail"
    assert _get(scenario, "result") != "pass"