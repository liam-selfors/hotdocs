import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "verifier-orchestrator"))
import verifier_orchestrator  # noqa: E402

FOO_COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [test-team]
depends_on: []
realizes: []
sealed: false
---

# Foo

## Purpose

A minimal component for exercising the verifier.
"""

FOO_LIBRARY_MD = "# Library\n\n```\ndo_the_thing(x) -> Thing\n```\n"

FOO_R001 = "# R-FOO-001\n\n**R-FOO-001** — Foo MUST add one to its input.\n"
FOO_R002 = "# R-FOO-002\n\n**R-FOO-002** — Foo MUST have a real, mutation-tested check.\n"
FOO_R003 = "# R-FOO-003\n\n**R-FOO-003** — Foo MUST read well to a judge.\n"

FOO_CODE_OK = """from dataclasses import dataclass


@dataclass
class Thing:
    value: int


def do_the_thing(x):
    return Thing(value=x + 1)
"""

FOO_CODE_DRIFT = """from dataclasses import dataclass


@dataclass
class Thing:
    value: int


def _do_the_thing_renamed(x):
    return Thing(value=x + 1)
"""


def write_foo(repo_root: Path, code: str = FOO_CODE_OK, extra_acceptance: dict[str, str] | None = None) -> None:
    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "interface" / "data").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(FOO_COMPONENT_MD, encoding="utf-8")
    (comp_dir / "interface" / "library.md").write_text(FOO_LIBRARY_MD, encoding="utf-8")
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(FOO_R001, encoding="utf-8")
    (comp_dir / "requirements" / "R-FOO-002.md").write_text(FOO_R002, encoding="utf-8")
    (comp_dir / "requirements" / "R-FOO-003.md").write_text(FOO_R003, encoding="utf-8")

    for name, text in (extra_acceptance or {}).items():
        (comp_dir / "acceptance" / name).write_text(text, encoding="utf-8")

    gen_dir = repo_root / "gen" / "foo"
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "foo.py").write_text(code, encoding="utf-8")


def acceptance_md(criterion_id: str, covers: str, kind: str, gherkin: str) -> str:
    return f"# {criterion_id}\n\nCovers: {covers}\nKind: {kind}\n\n```gherkin\n{gherkin}\n```\n"


@pytest.fixture
def repo_root(tmp_path):
    """verify() loads criterion-compiler/test-author dynamically from
    <repo_root>/{gen,pipeline}/ per call -- real copies must exist under
    tmp_path for compiled/generated-test dispatch to reach past the
    first dependency load."""
    shutil.copytree(REPO_ROOT / "pipeline" / "criterion-compiler", tmp_path / "pipeline" / "criterion-compiler")
    shutil.copytree(REPO_ROOT / "gen" / "test-author", tmp_path / "gen" / "test-author")
    shutil.copytree(REPO_ROOT / "gen" / "cache-manager", tmp_path / "gen" / "cache-manager")
    shutil.copytree(REPO_ROOT / "gen" / "llm-endpoint", tmp_path / "gen" / "llm-endpoint")
    return tmp_path
