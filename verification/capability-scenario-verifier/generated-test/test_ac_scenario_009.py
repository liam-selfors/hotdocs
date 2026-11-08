import shutil
import textwrap
from pathlib import Path

import pytest

import capability_scenario_verifier


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"))


_CAPABILITY_MD = """
---
id: P-X
title: Capability X
status: ratified
owners: [lselfors]
last_ratified_commit: deadbeef
---

# Capability X

### CS-X-001

Covers: P-X
Kind: compiled

```gherkin
Given a baseline
Then it holds
```
"""

_COMPONENT_MD = """
---
id: comp-foo
title: Foo Component
status: ratified
owners: [lselfors]
last_ratified_commit: deadbeef
realizes: [P-X]
sealed: false
---

# Foo Component
"""

_COMPILER_PRELUDE = """
class ParsedCriterion:
    def __init__(self, criterion_id, covers, kind, gherkin, file):
        self.criterion_id = criterion_id
        self.covers = covers
        self.kind = kind
        self.gherkin = gherkin
        self.file = file

"""


def _fake_compiler_source(result: dict) -> str:
    return _COMPILER_PRELUDE + (
        "def compile_criterion(parsed, surface=None):\n"
        f"    return {result!r}\n"
    )


def _make_repo(tmp_path: Path, compiler_result: dict) -> Path:
    repo_root = tmp_path / "repo"
    _write(repo_root / "specs" / "product" / "capx.md", _CAPABILITY_MD)
    _write(repo_root / "specs" / "components" / "foo" / "component.md", _COMPONENT_MD)
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "foo.py").write_text("X = 1\n")
    _write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        _fake_compiler_source(compiler_result),
    )
    return repo_root


def _find_real_compiler_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "pipeline" / "criterion-compiler" / "criterion_compiler.py"
        if candidate.is_file():
            return candidate.parent
    pytest.skip(
        "could not locate the live repository's pipeline/criterion-compiler/ "
        "relative to this test file"
    )


def test_compiled_scenario_passing_source_is_written_run_and_passes(tmp_path):
    repo_root = _make_repo(
        tmp_path,
        {"status": "compiled", "source": "def test_x():\n    assert True\n"},
    )

    report = capability_scenario_verifier.run_capability_scenarios(["comp-foo"], repo_root)

    expected_file = repo_root / "verification" / "capabilities" / "P-X" / "compiled" / "test_cs_x_001.py"
    assert expected_file.exists()
    assert expected_file.read_text() == "def test_x():\n    assert True\n"

    cap = _get(report, "P-X")
    assert cap is not None
    scenarios = _get(cap, "scenarios")
    assert len(scenarios) == 1
    scenario = scenarios[0]
    assert _get(scenario, "id") == "CS-X-001"
    assert _get(scenario, "kind") == "compiled"
    assert _get(scenario, "result") == "pass"


def test_compiled_scenario_failing_source_is_written_run_and_fails(tmp_path):
    repo_root = _make_repo(
        tmp_path,
        {"status": "compiled", "source": "def test_x():\n    assert False\n"},
    )

    report = capability_scenario_verifier.run_capability_scenarios(["comp-foo"], repo_root)

    expected_file = repo_root / "verification" / "capabilities" / "P-X" / "compiled" / "test_cs_x_001.py"
    assert expected_file.exists()
    assert expected_file.read_text() == "def test_x():\n    assert False\n"

    cap = _get(report, "P-X")
    scenarios = _get(cap, "scenarios")
    scenario = scenarios[0]
    assert _get(scenario, "result") == "fail"


def test_compile_error_is_fail_with_nothing_written(tmp_path):
    repo_root = _make_repo(
        tmp_path,
        {"status": "error", "message": "bad step"},
    )

    report = capability_scenario_verifier.run_capability_scenarios(["comp-foo"], repo_root)

    cap = _get(report, "P-X")
    scenarios = _get(cap, "scenarios")
    scenario = scenarios[0]
    assert _get(scenario, "result") == "fail"

    compiled_dir = repo_root / "verification" / "capabilities" / "P-X" / "compiled"
    assert not compiled_dir.exists() or not any(compiled_dir.iterdir())


def test_real_compiler_compiling_is_never_enough_for_a_pass(tmp_path):
    capability_md = """
    ---
    id: P-X
    title: Capability X
    status: ratified
    owners: [lselfors]
    last_ratified_commit: deadbeef
    ---

    # Capability X

    ### CS-X-001

    Covers: P-X
    Kind: compiled

    ```gherkin
    Given a x is 1
    Then x equals 1
    ```
    """

    repo_root = tmp_path / "repo"
    _write(repo_root / "specs" / "product" / "capx.md", capability_md)
    _write(repo_root / "specs" / "components" / "foo" / "component.md", _COMPONENT_MD)
    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "foo.py").write_text("X = 1\n")

    real_compiler_dir = _find_real_compiler_dir()
    dest = repo_root / "pipeline" / "criterion-compiler"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(real_compiler_dir, dest)

    report = capability_scenario_verifier.run_capability_scenarios(["comp-foo"], repo_root)

    cap = _get(report, "P-X")
    scenarios = _get(cap, "scenarios")
    scenario = scenarios[0]
    result = _get(scenario, "result")
    assert result == "fail"
    assert result != "pass"