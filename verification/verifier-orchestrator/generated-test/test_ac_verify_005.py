"""AC-VERIFY-005: a skipped llm-judge finding alone never causes an overall fail.

Given a component where every compiled and generated-test criterion passes,
its tests kill every mutant (mutation_score 1.0), interface_drift is false,
and the only llm-judge criterion is skipped (no judge injected),
When verify runs,
Then the overall verdict is pass.
"""

import verifier_orchestrator

from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(repo_root, rel, text):
    path = Path(repo_root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


FENCE = "```"

GLOSSARY = """# Glossary

- **Doubling** — multiplying a number by two.
"""

CAPABILITY = """---
id: P-DOUBLING
title: Doubling
status: draft
owners: [team-a]
---

# Doubling

## Purpose

The system doubles integers.

## Scope

- In scope: doubling integers.
- Out of scope: everything else.

## Capability scenarios

### CS-DOUBLING-001

Covers: P-DOUBLING
Kind: compiled

""" + FENCE + """gherkin
Given a n is 3
When double_value is invoked with [n]
Then value equals 6
""" + FENCE + "\n"

COMPONENT_MD = """---
id: comp-doubler
title: Doubler
status: draft
owners: [team-a]
depends_on: []
realizes: [P-DOUBLING]
---

# Doubler

## Purpose

Doubler doubles an integer and returns the doubled value.

## Scope

- In scope: doubling one integer.
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

None.

## Change log

- Initial draft.
"""

R_001 = """# R-DOUBLER-001

**R-DOUBLER-001** — `double_value(x)` MUST return an object whose `value` attribute is `2 * x`.
"""

R_002 = """# R-DOUBLER-002

**R-DOUBLER-002** — `double_value(x)` MUST double every integer input, including zero and negative numbers.
"""

R_003 = """# R-DOUBLER-003

**R-DOUBLER-003** — The interface documentation of `double_value` MUST be clear and free of contradiction.
"""

AC_001 = """# AC-DOUBLER-001

Covers: R-DOUBLER-001
Kind: compiled

""" + FENCE + """gherkin
Given a n is 3
When double_value is invoked with [n]
Then value equals 6
""" + FENCE + "\n"

AC_002 = """# AC-DOUBLER-002

Covers: R-DOUBLER-002
Kind: generated-test

""" + FENCE + """gherkin
Given any integer x, including zero and negative numbers
When double_value is called with x
Then the returned object's value attribute equals twice x
""" + FENCE + "\n"

AC_003 = """# AC-DOUBLER-003

Covers: R-DOUBLER-003
Kind: llm-judge

""" + FENCE + """gherkin
Given the interface documentation of double_value
When a reviewer reads it
Then it is clear and free of contradiction
""" + FENCE + "\n"

LIBRARY_MD = """# Library

""" + FENCE + """
double_value(x) -> object
""" + FENCE + """

`double_value` returns an object whose `value` attribute is `2 * x`.
"""

CONSTRAINTS_MD = """# Constraints

None.
"""

GEN_CODE = """import types as _types


def double_value(x) -> object:
    return _types.SimpleNamespace(value=x * 2)
"""

GENERATED_TEST_PATH = "verification/doubler/generated-test/test_ac_doubler_002.py"

GENERATED_TEST = """import doubler


def test_ac_doubler_002_doubles_every_input():
    for x, want in [(3, 6), (5, 10), (-4, -8), (7, 14), (0, 0)]:
        result = doubler.double_value(x)
        assert result.value == want
        assert type(result.value) is int
"""

FAKE_ASSEMBLER = '''import hashlib
from dataclasses import dataclass, field
from pathlib import Path


class _ReadOnlyMapping:
    def __getitem__(self, key):
        if key not in self.__dataclass_fields__:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key not in self.__dataclass_fields__:
            return default
        return getattr(self, key)

    def keys(self):
        return list(self.__dataclass_fields__)

    def values(self):
        return [getattr(self, k) for k in self.__dataclass_fields__]

    def items(self):
        return [(k, getattr(self, k)) for k in self.__dataclass_fields__]

    def __contains__(self, key):
        return key in self.__dataclass_fields__

    def __iter__(self):
        return iter(list(self.__dataclass_fields__))

    def __len__(self):
        return len(self.__dataclass_fields__)


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


def _body(path):
    text = Path(path).read_text(encoding="utf-8")
    if text.startswith("---\\n"):
        end = text.find("\\n---", 4)
        if end != -1:
            text = text[end + 4:]
    return text.strip()


def _join(texts):
    return "\\n\\n".join(t for t in (s.strip() for s in texts) if t)


def _component_dir(component_id, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    cdir = Path(repo_root) / "specs" / "components" / slug
    if not (cdir / "component.md").is_file():
        raise ValueError("unknown component id: " + component_id)
    return cdir


def _interface_text(cdir):
    idir = cdir / "interface"
    if not idir.is_dir():
        return ""
    return _join(_body(p) for p in sorted(idir.rglob("*.md")))


def _glossary(repo_root):
    g = Path(repo_root) / "specs" / "glossary.md"
    return _body(g) if g.is_file() else ""


def assemble(component_id, repo_root, mode="cold"):
    cdir = _component_dir(component_id, repo_root)
    reqs = sorted((cdir / "requirements").glob("R-*.md"))
    spec = _join([_body(cdir / "component.md")] + [_body(p) for p in reqs])
    interface = _interface_text(cdir)
    cpath = cdir / "constraints.md"
    constraints = _body(cpath) if cpath.is_file() else ""
    glossary = _glossary(repo_root)
    digest = hashlib.sha256(
        "\\x00".join([spec, interface, constraints, glossary]).encode("utf-8")
    ).hexdigest()
    hint = None
    if mode == "hint":
        hint = {}
        gdir = Path(repo_root) / "gen" / cdir.name
        if gdir.is_dir():
            for p in sorted(gdir.rglob("*")):
                if p.is_file():
                    hint[str(p.relative_to(gdir))] = p.read_text(encoding="utf-8")
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
    cdir = _component_dir(component_id, repo_root)
    apath = cdir / "acceptance" / (criterion_id + ".md")
    if not apath.is_file():
        raise ValueError("unknown criterion id: " + criterion_id)
    text = apath.read_text(encoding="utf-8")
    covers = ""
    for line in text.splitlines():
        if line.startswith("Covers:"):
            covers = line[len("Covers:"):].strip()
            break
    rpath = cdir / "requirements" / (covers + ".md")
    requirement_text = _body(rpath) if rpath.is_file() else ""
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=text.strip(),
        requirement_text=requirement_text,
        interface=_interface_text(cdir),
        glossary=_glossary(repo_root),
        dependency_interfaces={},
    )
'''


def _build_fixture(repo_root):
    _write(repo_root, "specs/glossary.md", GLOSSARY)
    _write(repo_root, "specs/product/doubling.md", CAPABILITY)
    base = "specs/components/doubler/"
    _write(repo_root, base + "component.md", COMPONENT_MD)
    _write(repo_root, base + "requirements/R-DOUBLER-001.md", R_001)
    _write(repo_root, base + "requirements/R-DOUBLER-002.md", R_002)
    _write(repo_root, base + "requirements/R-DOUBLER-003.md", R_003)
    _write(repo_root, base + "acceptance/AC-DOUBLER-001.md", AC_001)
    _write(repo_root, base + "acceptance/AC-DOUBLER-002.md", AC_002)
    _write(repo_root, base + "acceptance/AC-DOUBLER-003.md", AC_003)
    _write(repo_root, base + "interface/library.md", LIBRARY_MD)
    _write(repo_root, base + "constraints.md", CONSTRAINTS_MD)
    # The component's real (unsealed) code.
    _write(repo_root, "gen/doubler/doubler.py", GEN_CODE)
    # A cached generated-test for the generated-test criterion (R-VERIFY-002).
    _write(repo_root, GENERATED_TEST_PATH, GENERATED_TEST)
    # Fake spec-bundle-assembler, flat-module shape, matching its documented interface.
    _write(
        repo_root,
        "gen/spec-bundle-assembler/spec_bundle_assembler.py",
        FAKE_ASSEMBLER,
    )


def _test_author(bundle):
    # Fallback only: the cached test above should make this unnecessary.
    criterion_id = field(bundle, "criterion_id")
    if criterion_id == "AC-DOUBLER-002":
        return {
            "model_call_error": None,
            "file": {"path": GENERATED_TEST_PATH, "content": GENERATED_TEST},
        }
    return {"model_call_error": "unexpected criterion " + str(criterion_id), "file": None}


def test_skipped_llm_judge_alone_does_not_fail_overall(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    monkeypatch.chdir(repo_root)

    # No judge injected: every llm-judge criterion reports skipped.
    report = verifier_orchestrator.verify(
        "comp-doubler", repo_root, test_author=_test_author
    )

    as_dict = report.to_dict() if hasattr(report, "to_dict") else report
    criteria = field(report, "criteria")
    by_id = {field(c, "id"): c for c in criteria}

    # Given: the scenario the criterion describes actually holds.
    assert set(by_id) == {"AC-DOUBLER-001", "AC-DOUBLER-002", "AC-DOUBLER-003"}, as_dict
    assert field(by_id["AC-DOUBLER-001"], "kind") == "compiled", as_dict
    assert field(by_id["AC-DOUBLER-002"], "kind") == "generated-test", as_dict
    assert field(by_id["AC-DOUBLER-003"], "kind") == "llm-judge", as_dict

    for c in criteria:
        if field(c, "kind") in ("compiled", "generated-test"):
            assert field(c, "result") == "pass", as_dict

    llm_judge = [c for c in criteria if field(c, "kind") == "llm-judge"]
    assert len(llm_judge) == 1, as_dict
    assert field(llm_judge[0], "result") == "skipped", as_dict

    assert field(report, "interface_drift") is False, as_dict
    assert field(report, "mutation_score") == 1.0, as_dict

    # Then: the overall verdict is pass — a skipped finding alone never fails it.
    assert field(report, "overall") == "pass", as_dict
    assert field(as_dict, "overall") == "pass", as_dict