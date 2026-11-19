import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "gen" / "verifier-orchestrator"))
import verifier_orchestrator  # noqa: E402


def stamped(repo_root: Path, criterion_id: str, source: str, component_id: str = "comp-foo") -> str:
    """A cached generated test as test-author writes it (D320): the
    criterion header, computed from the bundle the real assembler builds
    for this fixture, then the test."""
    import hashlib
    import importlib.util

    path = REPO_ROOT / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py"
    spec = importlib.util.spec_from_file_location("_stamp_assembler", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_stamp_assembler"] = module
    spec.loader.exec_module(module)
    bundle = module.assemble_criterion(component_id, criterion_id, repo_root)

    def field(name):
        return bundle[name] if isinstance(bundle, dict) else getattr(bundle, name)

    digest = hashlib.sha256((field("criterion_text") + "\n" + field("requirement_text")).encode("utf-8")).hexdigest()
    return "# hotdocs-criterion: sha256:" + digest + "\n" + source

FOO_COMPONENT_MD_TEMPLATE = """---
id: comp-foo
title: Foo
status: draft
owners: [test-team]
depends_on: [{depends_on}]
realizes: [P-FOO]
sealed: false
---

# Foo

## Purpose

A minimal component for exercising the verifier.
"""
FOO_COMPONENT_MD = FOO_COMPONENT_MD_TEMPLATE.format(depends_on="")

BAR_COMPONENT_MD = """---
id: comp-bar
title: Bar
status: draft
owners: [test-team]
depends_on: []
sealed: true
source_path: fixtures/bar.py
---

# Bar

## Purpose

A minimal real dependency, for exercising dependency_interfaces.
"""
BAR_LIBRARY_MD = "# Library\n\n```\ndo_bar_thing(x: int) -> str\n```\n"
BAR_R001 = "# R-BAR-001\n\n**R-BAR-001** — Bar MUST stringify its input.\n"
BAR_AC001 = (
    "# AC-BAR-001\n\nCovers: R-BAR-001\nKind: compiled\n\n"
    "```gherkin\nGiven x is 1\nWhen do_bar_thing runs\nThen it returns a string\n```\n"
)


def write_bar(repo_root: Path) -> None:
    comp_dir = repo_root / "specs" / "components" / "bar"
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "interface").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(BAR_COMPONENT_MD, encoding="utf-8")
    (comp_dir / "interface" / "library.md").write_text(BAR_LIBRARY_MD, encoding="utf-8")
    (comp_dir / "requirements" / "R-BAR-001.md").write_text(BAR_R001, encoding="utf-8")
    (comp_dir / "acceptance" / "AC-BAR-001.md").write_text(BAR_AC001, encoding="utf-8")

# Real assemble_criterion() (R-VERIFY-009, D119) refuses a non-lint-clean
# corpus (R-ASSEMBLE-005) -- every requirement needs at least one covering
# acceptance file (R-LINT-008) even when a given test's own extra_acceptance
# only cares about one of them.
_BASELINE_ACCEPTANCE = {
    "AC-FOO-001.md": "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\n"
        "```gherkin\nGiven x is 1\nWhen do_the_thing runs\nThen value equals 2\n```\n",
    "AC-FOO-002.md": "# AC-FOO-002\n\nCovers: R-FOO-002\nKind: compiled\n\n"
        "```gherkin\nGiven the component\nWhen checked\nThen it is mutation-tested\n```\n",
    "AC-FOO-003.md": "# AC-FOO-003\n\nCovers: R-FOO-003\nKind: compiled\n\n"
        "```gherkin\nGiven the component\nWhen read\nThen it reads well\n```\n",
}

FOO_PRODUCT_MD = """---
id: P-FOO
title: Foo capability
status: draft
owners: [test-team]
---

# Foo capability

## Purpose

A minimal capability for the verifier's fixture component to realize.

## Scope

Fixture only.

## Capability scenario

### CS-FOO-001
Covers: P-FOO
Kind: generated-test

```gherkin
Given a fixture
When it is verified
Then it passes
```
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

# D124: two behaviorally distinct functions, each covered by its own
# generated-test criterion whose own test only exercises that one
# function -- for the union-mutation-score fix to be proven, each
# function needs its own mutable (comparison/int-constant) node a
# test scoped to the OTHER function could never kill.
FOO_CODE_TWO_FUNCTIONS = """from dataclasses import dataclass


@dataclass
class Thing:
    value: int


def do_the_thing(x):
    if x > 0:
        return Thing(value=x + 1)
    return Thing(value=0)


def double_it(x):
    if x >= 0:
        return x * 2
    return 0
"""

FOO_CODE_DRIFT = """from dataclasses import dataclass


@dataclass
class Thing:
    value: int


def _do_the_thing_renamed(x):
    return Thing(value=x + 1)
"""


def write_foo(
    repo_root: Path,
    code: str = FOO_CODE_OK,
    extra_acceptance: dict[str, str] | None = None,
    depends_on: list[str] | None = None,
) -> None:
    comp_dir = repo_root / "specs" / "components" / "foo"
    (comp_dir / "requirements").mkdir(parents=True, exist_ok=True)
    (comp_dir / "interface" / "data").mkdir(parents=True, exist_ok=True)
    (comp_dir / "acceptance").mkdir(parents=True, exist_ok=True)
    component_md = FOO_COMPONENT_MD_TEMPLATE.format(depends_on=", ".join(depends_on or []))
    (comp_dir / "component.md").write_text(component_md, encoding="utf-8")
    product_dir = repo_root / "specs" / "product"
    product_dir.mkdir(parents=True, exist_ok=True)
    (product_dir / "foo.md").write_text(FOO_PRODUCT_MD, encoding="utf-8")
    (comp_dir / "interface" / "library.md").write_text(FOO_LIBRARY_MD, encoding="utf-8")
    (comp_dir / "requirements" / "R-FOO-001.md").write_text(FOO_R001, encoding="utf-8")
    (comp_dir / "requirements" / "R-FOO-002.md").write_text(FOO_R002, encoding="utf-8")
    (comp_dir / "requirements" / "R-FOO-003.md").write_text(FOO_R003, encoding="utf-8")

    for name, text in _BASELINE_ACCEPTANCE.items():
        (comp_dir / "acceptance" / name).write_text(text, encoding="utf-8")

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
    shutil.copytree(REPO_ROOT / "gen" / "spec-bundle-assembler", tmp_path / "gen" / "spec-bundle-assembler")
    shutil.copytree(REPO_ROOT / "gen" / "spec-linter", tmp_path / "gen" / "spec-linter")
    shutil.copytree(REPO_ROOT / "gen" / "graph-query-engine", tmp_path / "gen" / "graph-query-engine")
    # The python adapter every component has (D344): found under repo_root first.
    shutil.copytree(REPO_ROOT / "gen" / "kind-python", tmp_path / "gen" / "kind-python")
    # spec-linter loads these since the D242 split; a copied component takes
    # tmp_path for the tool root, so they must be here too.
    for slug in ("corpus-loader", "citation-checker", "size-checker"):
        shutil.copytree(REPO_ROOT / "gen" / slug, tmp_path / "gen" / slug)
    (tmp_path / "specs").mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "specs" / "glossary.md", tmp_path / "specs" / "glossary.md")
    return tmp_path
