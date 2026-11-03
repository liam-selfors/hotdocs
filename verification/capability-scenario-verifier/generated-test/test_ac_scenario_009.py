import shutil
from pathlib import Path

import pytest

import capability_scenario_verifier


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


FAKE_COMPILER_TEMPLATE = '''\
class ParsedCriterion:
    def __init__(self, criterion_id=None, covers=None, kind=None, gherkin=None, file=None):
        self.criterion_id = criterion_id
        self.covers = covers
        self.kind = kind
        self.gherkin = gherkin
        self.file = file


_RESULT = {result!r}


def compile_criterion(parsed, surface=None):
    return dict(_RESULT)
'''


def _write_fake_compiler(repo_root: Path, result: dict) -> None:
    compiler_dir = repo_root / "pipeline" / "criterion-compiler"
    compiler_dir.mkdir(parents=True, exist_ok=True)
    (compiler_dir / "criterion_compiler.py").write_text(
        FAKE_COMPILER_TEMPLATE.format(result=result)
    )


COMPONENT_MD_TEMPLATE = '''\
---
id: comp-{slug}
title: Demo Component
status: draft
owners: [lselfors@gmail.com]
realizes: [{capability_id}]
sealed: false
---

## Purpose

A synthetic component realizing {capability_id} for test purposes.
'''


def _write_component_fixture(repo_root: Path, slug: str, capability_id: str) -> None:
    component_dir = repo_root / "specs" / "components" / slug
    component_dir.mkdir(parents=True, exist_ok=True)
    (component_dir / "component.md").write_text(
        COMPONENT_MD_TEMPLATE.format(slug=slug, capability_id=capability_id)
    )
    module_name = slug.replace("-", "_")
    gen_dir = repo_root / "gen" / slug
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / f"{module_name}.py").write_text("# stub component module\n")


CAPABILITY_MD_TEMPLATE = '''\
---
id: {capability_id}
title: Demo Capability
status: draft
owners: [lselfors@gmail.com]
---

### {scenario_id}

Covers: {capability_id}
Kind: {kind}

```gherkin
{gherkin}
```
'''


def _write_capability_fixture(
    repo_root: Path, capability_id: str, scenario_id: str, kind: str, gherkin: str
) -> None:
    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True, exist_ok=True)
    name = capability_id.lower().replace("_", "-")
    (product_dir / f"{name}.md").write_text(
        CAPABILITY_MD_TEMPLATE.format(
            capability_id=capability_id,
            scenario_id=scenario_id,
            kind=kind,
            gherkin=gherkin,
        )
    )


def _report_for_scenario(report, capability_id, scenario_id):
    capability_report = _get(report, capability_id)
    scenarios = _get(capability_report, "scenarios")
    for scenario in scenarios:
        if _get(scenario, "id") == scenario_id:
            return scenario
    raise AssertionError(f"scenario {scenario_id} not found in report")


def _locate_live_repo_root():
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        cc_dir = parent / "pipeline" / "criterion-compiler"
        if (cc_dir / "criterion_compiler.py").exists() or (
            cc_dir / "criterion_compiler" / "__init__.py"
        ).exists():
            return parent
    return None


def test_compiled_scenario_passes_when_source_test_passes(tmp_path):
    repo_root = tmp_path
    capability_id = "P-X"
    scenario_id = "CS-X-001"
    slug = "demo-comp-pass"

    _write_component_fixture(repo_root, slug, capability_id)
    _write_capability_fixture(
        repo_root,
        capability_id,
        scenario_id,
        "compiled",
        "Given a compiled scenario CS-X-001\nThen it compiles",
    )
    _write_fake_compiler(
        repo_root,
        {"status": "compiled", "source": "def test_x():\n    assert True\n"},
    )

    report = capability_scenario_verifier.run_capability_scenarios(
        [f"comp-{slug}"], repo_root
    )

    expected_file = (
        repo_root
        / "verification"
        / "capabilities"
        / capability_id
        / "compiled"
        / "test_cs_x_001.py"
    )
    assert expected_file.is_file()
    assert "assert True" in expected_file.read_text()

    scenario = _report_for_scenario(report, capability_id, scenario_id)
    assert _get(scenario, "result") == "pass"


def test_compiled_scenario_fails_when_source_test_fails(tmp_path):
    repo_root = tmp_path
    capability_id = "P-X"
    scenario_id = "CS-X-001"
    slug = "demo-comp-fail"

    _write_component_fixture(repo_root, slug, capability_id)
    _write_capability_fixture(
        repo_root,
        capability_id,
        scenario_id,
        "compiled",
        "Given a compiled scenario CS-X-001\nThen it compiles",
    )
    _write_fake_compiler(
        repo_root,
        {"status": "compiled", "source": "def test_x():\n    assert False\n"},
    )

    report = capability_scenario_verifier.run_capability_scenarios(
        [f"comp-{slug}"], repo_root
    )

    expected_file = (
        repo_root
        / "verification"
        / "capabilities"
        / capability_id
        / "compiled"
        / "test_cs_x_001.py"
    )
    assert expected_file.is_file()

    scenario = _report_for_scenario(report, capability_id, scenario_id)
    assert _get(scenario, "result") == "fail"


def test_compiler_error_status_is_fail_with_nothing_written(tmp_path):
    repo_root = tmp_path
    capability_id = "P-X"
    scenario_id = "CS-X-001"
    slug = "demo-comp-error"

    _write_component_fixture(repo_root, slug, capability_id)
    _write_capability_fixture(
        repo_root,
        capability_id,
        scenario_id,
        "compiled",
        "Given a compiled scenario CS-X-001\nThen it compiles",
    )
    _write_fake_compiler(repo_root, {"status": "error", "message": "bad step"})

    report = capability_scenario_verifier.run_capability_scenarios(
        [f"comp-{slug}"], repo_root
    )

    compiled_dir = (
        repo_root / "verification" / "capabilities" / capability_id / "compiled"
    )
    assert not compiled_dir.exists() or not any(compiled_dir.iterdir())

    scenario = _report_for_scenario(report, capability_id, scenario_id)
    assert _get(scenario, "result") == "fail"


def test_real_compiler_compiling_alone_is_not_a_pass(tmp_path):
    live_repo_root = _locate_live_repo_root()
    if live_repo_root is None:
        pytest.skip("live repository root with pipeline/criterion-compiler not found")

    repo_root = tmp_path
    capability_id = "P-X"
    scenario_id = "CS-X-001"
    slug = "demo-comp-real"

    _write_component_fixture(repo_root, slug, capability_id)
    _write_capability_fixture(
        repo_root,
        capability_id,
        scenario_id,
        "compiled",
        "Given a x is 1\nThen x equals 1",
    )

    src = live_repo_root / "pipeline" / "criterion-compiler"
    dst = repo_root / "pipeline" / "criterion-compiler"
    shutil.copytree(src, dst)

    report = capability_scenario_verifier.run_capability_scenarios(
        [f"comp-{slug}"], repo_root
    )

    scenario = _report_for_scenario(report, capability_id, scenario_id)
    assert _get(scenario, "result") == "fail"
    assert _get(scenario, "result") != "pass"