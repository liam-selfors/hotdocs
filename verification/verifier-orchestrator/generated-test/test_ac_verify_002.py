import verifier_orchestrator

import hashlib
import json
from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FAKE_ASSEMBLER = '''from dataclasses import dataclass, field as _dc_field
from pathlib import Path
import hashlib


class _MappingMixin:
    def __getitem__(self, key):
        if key not in self.__dataclass_fields__:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self.__dataclass_fields__:
            return getattr(self, key)
        return default

    def keys(self):
        return list(self.__dataclass_fields__.keys())

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.__dataclass_fields__)

    def __contains__(self, key):
        return key in self.__dataclass_fields__


@dataclass
class SpecBundle(_MappingMixin):
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = _dc_field(default_factory=dict)
    dependency_context: dict = _dc_field(default_factory=dict)
    dependency_usage: dict = _dc_field(default_factory=dict)
    vars: dict = _dc_field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None


@dataclass
class CriterionBundle(_MappingMixin):
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = _dc_field(default_factory=dict)


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _read(path):
    p = Path(path)
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def _join(texts):
    return "\\n\\n".join(t for t in texts if t)


def _interface_text(base):
    iface = base / "interface"
    if not iface.is_dir():
        return ""
    return _join(_read(p) for p in sorted(iface.rglob("*.md")))


def assemble(component_id, repo_root, mode="cold"):
    repo_root = Path(repo_root)
    base = repo_root / "specs" / "components" / _slug(component_id)
    spec = _join([_read(base / "component.md")] + [_read(p) for p in sorted((base / "requirements").glob("*.md"))])
    interface = _interface_text(base)
    constraints = _read(base / "constraints.md")
    glossary = _read(repo_root / "specs" / "glossary.md")
    digest = hashlib.sha256((spec + interface + constraints + glossary).encode("utf-8")).hexdigest()
    hint = None
    if mode == "hint":
        gen_dir = repo_root / "gen" / _slug(component_id)
        hint = {str(p.relative_to(gen_dir)): p.read_text(encoding="utf-8") for p in gen_dir.rglob("*.py")} if gen_dir.is_dir() else {}
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + digest,
        spec=spec,
        interface=interface,
        constraints=constraints,
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary=glossary,
        hint_code=hint,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    repo_root = Path(repo_root)
    base = repo_root / "specs" / "components" / _slug(component_id)
    criterion_text = _read(base / "acceptance" / (criterion_id + ".md"))
    covers = ""
    for line in criterion_text.splitlines():
        if line.startswith("Covers:"):
            covers = line.split(":", 1)[1].strip()
            break
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=criterion_text,
        requirement_text=_read(base / "requirements" / (covers + ".md")),
        interface=_interface_text(base),
        glossary=_read(repo_root / "specs" / "glossary.md"),
        dependency_interfaces={},
    )
'''


def _build_fixture(repo_root: Path, log_dir: Path, slug: str, impl_body: str) -> dict:
    upper = slug.upper()
    component_id = f"comp-{slug}"
    module_name = slug.replace("-", "_")
    criterion_id = f"AC-{upper}-001"
    requirement_id = f"R-{upper}-001"
    capability_id = f"P-{upper}"

    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )

    _write(
        repo_root / "specs" / "product" / f"{slug}.md",
        f"""---
id: {capability_id}
title: Widget capability
status: draft
owners: [team-a]
---

# Widget capability

## Purpose

Widgets double numbers.

## Scope

- In scope: doubling a number.
- Out of scope: everything else.

## Capability scenarios

### CS-{upper}-001

Covers: {capability_id}
Kind: generated-test

```gherkin
Given the widget system is assembled
When a number is doubled
Then the doubled number is returned
```
""",
    )

    comp_dir = repo_root / "specs" / "components" / slug
    _write(
        comp_dir / "component.md",
        f"""---
id: {component_id}
title: Widget {slug}
status: draft
owners: [team-a]
realizes: [{capability_id}]
depends_on: []
---

# Widget {slug}

## Purpose

Widget doubles a number.

## Scope

- In scope: doubling a number.
- Out of scope: everything else.

## Definitions

None.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

## Change log

- Initial draft.
""",
    )
    _write(
        comp_dir / "requirements" / f"{requirement_id}.md",
        f"# {requirement_id}\n\n**{requirement_id}** — `double_it(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp_dir / "acceptance" / f"{criterion_id}.md",
        f"""# {criterion_id}

Covers: {requirement_id}
Kind: generated-test

```gherkin
Given the widget module is importable
When double_it is called with 2
Then it returns 4
```
""",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\ndouble_it(x: int) -> int\n```\n",
    )
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")

    # The real generated code under test.
    _write(
        repo_root / "gen" / slug / f"{module_name}.py",
        f"def double_it(x: int) -> int:\n    return {impl_body}\n",
    )

    # Fake spec-bundle-assembler dependency, planted at the documented path.
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        FAKE_ASSEMBLER,
    )

    # The already-generated test, at the glossary's "Criterion test filename".
    run_log = log_dir / f"{slug}-runs.log"
    test_filename = "test_" + criterion_id.lower().replace("-", "_") + ".py"
    _write(
        repo_root / "verification" / slug / "generated-test" / test_filename,
        f"""import pathlib
import {module_name}


def test_double_it_returns_twice_the_input():
    with open({str(run_log)!r}, "a", encoding="utf-8") as fh:
        fh.write(str(pathlib.Path({module_name}.__file__).resolve()) + "\\n")
    assert {module_name}.double_it(2) == 4
""",
    )

    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "requirement_id": requirement_id,
        "module_name": module_name,
        "run_log": run_log,
    }


@pytest.mark.parametrize(
    "slug, impl_body, expected",
    [
        ("widgeta", "2 * x", "pass"),
        ("widgetb", "2 * x + 1", "fail"),
    ],
)
def test_cached_generated_test_is_executed_against_gen_and_reported(
    tmp_path, slug, impl_body, expected
):
    repo_root = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    log_dir.mkdir(parents=True)
    info = _build_fixture(repo_root, log_dir, slug, impl_body)

    author_log = log_dir / f"{slug}-author.log"

    def recording_test_author(bundle):
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {"model_call_error": "test_author must not be called on a cache hit", "file": None}

    report = verifier_orchestrator.verify(
        info["component_id"], repo_root, judge=None, test_author=recording_test_author
    )

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == info["criterion_id"]]
    assert len(matching) == 1, f"criterion {info['criterion_id']} missing from report: {criteria!r}"
    entry = matching[0]

    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") == expected

    # The already-present test was used as-is: test_author was never dispatched.
    assert not author_log.exists(), "test_author was called despite a cached test file"
    assert "test_authoring" not in entry if isinstance(entry, dict) else True

    # The test actually ran, importing the component's code from gen/<component>/.
    assert info["run_log"].exists(), "cached generated test was never executed"
    gen_module = (repo_root / "gen" / slug / f"{info['module_name']}.py").resolve()
    ran_paths = [
        Path(line.strip())
        for line in info["run_log"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(p == gen_module for p in ran_paths), (
        f"test was not executed against gen/{slug}/: {ran_paths!r}"
    )