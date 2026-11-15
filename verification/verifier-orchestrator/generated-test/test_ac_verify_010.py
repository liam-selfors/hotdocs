"""AC-VERIFY-010: a generated-test criterion with no cached test and no
test_author configured is recorded as ``fail`` (not ``skipped``), and the
overall verdict is ``fail`` (R-VERIFY-010)."""

import json
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = """# Glossary

- **Widget** — a test term.
"""

PRODUCT = """---
id: P-WIDGET
title: Widget Capability
status: draft
owners: [team-a]
---

# Widget Capability

## Purpose

Doubling numbers.

## Scope

- In scope: doubling a number.

### CS-WIDGET-001

Covers: P-WIDGET
Kind: compiled

```gherkin
Given a x is 2
When widget.double is invoked with [x]
Then result equals 4
```
"""

COMPONENT_MD = """---
id: comp-widget
title: Widget
status: draft
owners: [team-a]
realizes: [P-WIDGET]
depends_on: []
---

# Widget

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
"""

REQUIREMENT = """# R-WIDGET-001

**R-WIDGET-001** — `double(x)` MUST return `2 * x`.
"""

ACCEPTANCE = """# AC-WIDGET-001

Covers: R-WIDGET-001
Kind: generated-test

```gherkin
Given x = 2
When double(x) is called
Then it returns 4
```
"""

LIBRARY = """# Library

```
double(x: int) -> int
```
"""

CONSTRAINTS = """# Constraints

None.
"""

GEN_MODULE = """def double(x):
    return 2 * x
"""

FAKE_ASSEMBLER = r'''
import dataclasses
import hashlib
import re
from pathlib import Path


def _strip_frontmatter(text):
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            nl = text.find("\n", end + 4)
            return text[nl + 1:] if nl != -1 else ""
    return text


def _join(parts):
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


class _MappingMixin:
    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())

    def __contains__(self, key):
        return key in self.keys()


@dataclasses.dataclass
class SpecBundle(_MappingMixin):
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)
    dependency_context: dict = dataclasses.field(default_factory=dict)
    dependency_usage: dict = dataclasses.field(default_factory=dict)
    vars: dict = dataclasses.field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None


@dataclasses.dataclass
class CriterionBundle(_MappingMixin):
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)


def _component_dir(component_id, repo_root):
    return Path(repo_root) / "specs" / "components" / _slug(component_id)


def _interface_text(cdir):
    idir = cdir / "interface"
    parts = []
    if idir.is_dir():
        for p in sorted(idir.rglob("*.md")):
            parts.append(p.read_text(encoding="utf-8"))
    return _join(parts)


def _glossary(repo_root):
    g = Path(repo_root) / "specs" / "glossary.md"
    return g.read_text(encoding="utf-8").strip() if g.is_file() else ""


def assemble(component_id, repo_root, mode="cold"):
    cdir = _component_dir(component_id, repo_root)
    spec_parts = [_strip_frontmatter((cdir / "component.md").read_text(encoding="utf-8"))]
    rdir = cdir / "requirements"
    if rdir.is_dir():
        for p in sorted(rdir.glob("R-*.md")):
            spec_parts.append(p.read_text(encoding="utf-8"))
    spec = _join(spec_parts)
    interface = _interface_text(cdir)
    cpath = cdir / "constraints.md"
    constraints = cpath.read_text(encoding="utf-8").strip() if cpath.is_file() else ""
    glossary = _glossary(repo_root)
    digest = hashlib.sha256(
        "\0".join([spec, interface, constraints, glossary]).encode("utf-8")
    ).hexdigest()
    hint_code = None
    if mode == "hint":
        hint_code = {}
        gdir = Path(repo_root) / "gen" / _slug(component_id)
        if gdir.is_dir():
            for p in sorted(gdir.rglob("*")):
                if p.is_file():
                    hint_code[str(p.relative_to(gdir))] = p.read_text(encoding="utf-8")
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + digest,
        spec=spec,
        interface=interface,
        constraints=constraints,
        glossary=glossary,
        hint_code=hint_code,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    cdir = _component_dir(component_id, repo_root)
    text = (cdir / "acceptance" / (criterion_id + ".md")).read_text(encoding="utf-8")
    m = re.search(r"Covers:\s*(\S+)", text)
    covers = m.group(1) if m else ""
    g = re.search(r"```gherkin\n(.*?)```", text, re.S)
    criterion_text = g.group(1).strip() if g else text.strip()
    rpath = cdir / "requirements" / (covers + ".md")
    requirement_text = rpath.read_text(encoding="utf-8").strip() if rpath.is_file() else ""
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=criterion_text,
        requirement_text=requirement_text,
        interface=_interface_text(cdir),
        glossary=_glossary(repo_root),
    )
'''


def _build_fixture(repo_root):
    repo_root = Path(repo_root)
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "widget.md", PRODUCT)
    cdir = repo_root / "specs" / "components" / SLUG
    _write(cdir / "component.md", COMPONENT_MD)
    _write(cdir / "requirements" / f"{REQUIREMENT_ID}.md", REQUIREMENT)
    _write(cdir / "acceptance" / f"{CRITERION_ID}.md", ACCEPTANCE)
    _write(cdir / "interface" / "library.md", LIBRARY)
    _write(cdir / "constraints.md", CONSTRAINTS)
    # The component's real generated code.
    _write(repo_root / "gen" / SLUG / "widget.py", GEN_MODULE)
    # Fake spec-bundle-assembler, flat-module shape, planted at repo_root.
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        FAKE_ASSEMBLER,
    )
    return repo_root


def _assert_no_cached_test(repo_root):
    cached = (
        Path(repo_root)
        / "verification"
        / SLUG
        / "generated-test"
        / "test_ac_widget_001.py"
    )
    assert not cached.exists()


def _find_criterion(criteria):
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, f"expected exactly one {CRITERION_ID} entry, got {criteria!r}"
    return matches[0]


def test_unauthored_generated_test_criterion_fails_not_skipped(tmp_path):
    repo_root = _build_fixture(tmp_path / "repo")
    _assert_no_cached_test(repo_root)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    criteria = field(report, "criteria")
    entry = _find_criterion(criteria)
    assert field(entry, "kind") == "generated-test"
    result = field(entry, "result")
    assert result != "skipped"
    assert result == "fail"
    assert field(report, "overall") == "fail"


def test_unauthored_generated_test_criterion_fails_explicit_none(tmp_path):
    repo_root = _build_fixture(tmp_path / "repo")
    _assert_no_cached_test(repo_root)

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, judge=None, test_author=None
    )

    entry = _find_criterion(field(report, "criteria"))
    assert field(entry, "result") == "fail"
    assert field(report, "overall") == "fail"

    as_dict = report.to_dict()
    dict_entry = _find_criterion(as_dict["criteria"])
    assert dict_entry["result"] == "fail"
    assert as_dict["overall"] == "fail"


def test_cli_reports_fail_for_unauthored_generated_test(tmp_path, capsys):
    repo_root = _build_fixture(tmp_path / "repo")
    _assert_no_cached_test(repo_root)

    code = verifier_orchestrator.main(
        [COMPONENT_ID, f"--repo-root={repo_root}", "--format=json"]
    )
    out = capsys.readouterr().out

    assert code == 1
    data = json.loads(out)
    entry = _find_criterion(data["criteria"])
    assert entry["result"] == "fail"
    assert data["overall"] == "fail"