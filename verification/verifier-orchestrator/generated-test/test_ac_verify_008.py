import verifier_orchestrator

import json
from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FAKE_ASSEMBLER = '''from dataclasses import dataclass, field
from pathlib import Path


class _ReadOnlyMapping:
    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __contains__(self, key):
        return hasattr(self, key)

    def keys(self):
        return list(self.__dataclass_fields__.keys())


@dataclass
class SpecBundle(_ReadOnlyMapping):
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = field(default_factory=dict)
    dependency_context: dict = field(default_factory=dict)
    dependency_usage: dict = field(default_factory=dict)
    vars: dict = field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None


@dataclass
class CriterionBundle(_ReadOnlyMapping):
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = field(default_factory=dict)


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _read(path):
    p = Path(path)
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def _interface_text(base):
    parts = []
    idir = base / "interface"
    if idir.is_dir():
        for p in sorted(idir.rglob("*.md")):
            t = _read(p)
            if t:
                parts.append(t)
    return "\\n\\n".join(parts)


def assemble(component_id, repo_root, mode="cold"):
    base = Path(repo_root) / "specs" / "components" / _slug(component_id)
    spec_parts = [_read(base / "component.md")]
    rdir = base / "requirements"
    if rdir.is_dir():
        spec_parts += [_read(p) for p in sorted(rdir.glob("R-*.md"))]
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "0" * 64,
        spec="\\n\\n".join(s for s in spec_parts if s),
        interface=_interface_text(base),
        constraints=_read(base / "constraints.md"),
        glossary=_read(Path(repo_root) / "specs" / "glossary.md"),
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    base = Path(repo_root) / "specs" / "components" / _slug(component_id)
    ac_text = _read(base / "acceptance" / (criterion_id + ".md"))
    covers = ""
    for line in ac_text.splitlines():
        if line.startswith("Covers:"):
            covers = line.split(":", 1)[1].strip()
            break
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=ac_text,
        requirement_text=_read(base / "requirements" / (covers + ".md")),
        interface=_interface_text(base),
        glossary=_read(Path(repo_root) / "specs" / "glossary.md"),
        dependency_interfaces={},
    )
'''


COMPONENT_MD = """---
id: comp-gizmo
title: Gizmo
status: draft
owners: [team-a]
realizes: [P-GIZMO]
depends_on: []
---

# Gizmo

## Purpose

Gizmo doubles a number.

## Scope

- In scope: doubling an integer.
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

PRODUCT_MD = """---
id: P-GIZMO
title: Gizmo capability
status: draft
owners: [team-a]
---

# Gizmo capability

## Purpose

Numbers can be doubled.

## Scope

- In scope: doubling.

### CS-GIZMO-001

Covers: P-GIZMO
Kind: llm-judge

```gherkin
Given a number
When it is doubled
Then the result is twice the number
```
"""

GLOSSARY_MD = """# Glossary

- **Gizmo term** — a test term.
"""

R1 = "# R-GIZMO-001\n\n**R-GIZMO-001** — The interface text for `double_it(x)` MUST be clear and unambiguous.\n"
R2 = "# R-GIZMO-002\n\n**R-GIZMO-002** — `double_it(x)` MUST return `2 * x`.\n"

AC1 = """# AC-GIZMO-001

Covers: R-GIZMO-001
Kind: llm-judge

```gherkin
Given the gizmo interface text
When a reviewer reads it
Then the meaning of double_it is unambiguous
```
"""

AC2 = """# AC-GIZMO-002

Covers: R-GIZMO-002
Kind: generated-test

```gherkin
Given x = 3
When double_it(x) is called
Then it returns 6
```
"""

LIBRARY_MD = """# Library

```
double_it(x: int) -> int
```
"""

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

GEN_CODE = '''def double_it(x: int) -> int:
    """Return twice x."""
    return 2 * x
'''

CACHED_TEST = '''import gizmo


def test_double_it_returns_twice_its_input():
    assert gizmo.double_it(3) == 6
    assert gizmo.double_it(0) == 0
    assert gizmo.double_it(-2) == -4
'''


def _build_fixture(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    _write(repo_root / "specs" / "product" / "gizmo.md", PRODUCT_MD)
    comp = repo_root / "specs" / "components" / "gizmo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-GIZMO-001.md", R1)
    _write(comp / "requirements" / "R-GIZMO-002.md", R2)
    _write(comp / "acceptance" / "AC-GIZMO-001.md", AC1)
    _write(comp / "acceptance" / "AC-GIZMO-002.md", AC2)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(repo_root / "gen" / "gizmo" / "gizmo.py", GEN_CODE)
    _write(
        repo_root / "verification" / "gizmo" / "generated-test" / "test_ac_gizmo_002.py",
        CACHED_TEST,
    )
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        FAKE_ASSEMBLER,
    )


def _snapshot(root: Path, sub: str) -> dict:
    base = root / sub
    out = {}
    for p in sorted(base.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts and not p.name.endswith(".pyc"):
            out[str(p.relative_to(root))] = p.read_bytes()
    return out


def _report_dict(report):
    if hasattr(report, "to_dict"):
        return report.to_dict()
    return report


def test_ac_verify_008_verify_twice_yields_identical_reports(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    judge_calls = []

    def judge(bundle):
        judge_calls.append(1)
        return {"result": "pass", "rationale": "The interface text is unambiguous."}

    gen_before = _snapshot(repo_root, "gen/gizmo")
    acc_before = _snapshot(repo_root, "specs/components/gizmo/acceptance")

    first = verifier_orchestrator.verify("comp-gizmo", repo_root, judge=judge)

    # The Given: gen/<component>/ and acceptance/ content stay unchanged between runs.
    assert _snapshot(repo_root, "gen/gizmo") == gen_before
    assert _snapshot(repo_root, "specs/components/gizmo/acceptance") == acc_before
    calls_after_first = len(judge_calls)

    second = verifier_orchestrator.verify("comp-gizmo", repo_root, judge=judge)

    assert _snapshot(repo_root, "gen/gizmo") == gen_before
    assert _snapshot(repo_root, "specs/components/gizmo/acceptance") == acc_before

    # The judge was actually consulted on each run (the llm-judge criterion was evaluated).
    assert calls_after_first >= 1
    assert len(judge_calls) - calls_after_first == calls_after_first

    d1 = _report_dict(first)
    d2 = _report_dict(second)

    # Sanity: the reports describe the fixture component and its criteria.
    assert field(d1, "component_id") == "comp-gizmo"
    ids1 = sorted(field(c, "id") for c in field(d1, "criteria"))
    assert ids1 == ["AC-GIZMO-001", "AC-GIZMO-002"]
    judged = [c for c in field(d1, "criteria") if field(c, "id") == "AC-GIZMO-001"][0]
    assert field(judged, "result") == "pass"

    # Then: the two VerificationReports are identical.
    assert json.dumps(d1, sort_keys=True, default=str) == json.dumps(d2, sort_keys=True, default=str)
    assert d1 == d2
    assert field(first, "overall") == field(second, "overall")
    assert field(first, "criteria") == field(second, "criteria")
    assert field(first, "requirement_results") == field(second, "requirement_results")
    assert field(first, "interface_drift") == field(second, "interface_drift")
    assert field(first, "mutation_score") == field(second, "mutation_score")
    assert first == second