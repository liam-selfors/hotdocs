import verifier_orchestrator

import json
from pathlib import Path

import pytest


COMPONENT_ID = "comp-label-maker"
SLUG = "label-maker"
MODULE_NAME = "label_maker"
CRITERION_ID = "AC-LABEL-001"
REQUIREMENT_ID = "R-LABEL-001"
TEST_FILENAME = "test_ac_label_001.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


# The candidate module: exactly four mutation sites under R-VERIFY-006's
# operator set:
#   1. `x > 10`        -> `x <= 10`
#   2. `x < 0`         -> `x >= 0`
#   3. `... and ...`   -> `... or ...`
#   4. `x * 2`         -> `x / 2`
# No boolean constants, no chained comparisons, and numeric constants are
# never mutated.
CANDIDATE_SOURCE = '''def clamp_label(x, strict):
    if x > 10:
        return "high"
    if x < 0 and strict:
        return "negative"
    return str(x * 2)
'''

# A weak but passing test. Against the real code it passes. Of the four
# mutants, only `x <= 10` changes the result for (20, False) (it yields
# "40"), so the test kills exactly one mutant: score 1/4 = 0.25, below 0.8.
WEAK_TEST_SOURCE = '''import label_maker


def test_large_value_is_high():
    assert label_maker.clamp_label(20, False) == "high"
'''


COMPONENT_MD = """---
id: comp-label-maker
title: Label Maker
status: draft
owners: [team-a]
realizes: [P-LABELS]
depends_on: []
---

# Label Maker

## Purpose

Label Maker turns a number into a short label.

## Scope

- In scope: labelling numbers.
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
id: P-LABELS
title: Labels
status: draft
owners: [team-a]
---

# Labels

## Purpose

Numbers get short labels.

## Scope

- In scope: labelling numbers.

## Capability scenarios

### CS-LABELS-001

Covers: P-LABELS
Kind: generated-test

```gherkin
Given a number
When it is labelled
Then a label is returned
```
"""

GLOSSARY_MD = """# Glossary

- **Label** — a short text describing a number.
"""

REQUIREMENT_MD = """# R-LABEL-001

**R-LABEL-001** — `clamp_label(x, strict)` MUST return `"high"` when `x` exceeds 10.
"""

ACCEPTANCE_MD = """# AC-LABEL-001

Covers: R-LABEL-001
Kind: generated-test

```gherkin
Given x is 20 and strict is false
When clamp_label is called with them
Then it returns "high"
```
"""

LIBRARY_MD = """# Library

```
clamp_label(x: int, strict: bool) -> str
```
"""

CONSTRAINTS_MD = """# Constraints

None.
"""

# A fake spec-bundle-assembler matching its documented library signatures
# and SpecBundle / CriterionBundle shapes (dataclasses that also read as
# read-only mappings). Planted so verify never depends on linting this
# fixture through the real assembler.
FAKE_ASSEMBLER_SOURCE = '''import dataclasses
import hashlib
from pathlib import Path


class _MappingMixin:
    def __getitem__(self, key):
        if key not in self.keys():
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self.keys():
            return getattr(self, key)
        return default

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]

    def items(self):
        return [(k, getattr(self, k)) for k in self.keys()]

    def values(self):
        return [getattr(self, k) for k in self.keys()]

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


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _read(path):
    path = Path(path)
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _join(texts):
    return "\\n\\n".join(t.strip() for t in texts if t and t.strip())


def _interface_text(comp_dir):
    iface = comp_dir / "interface"
    if not iface.is_dir():
        return ""
    return _join(_read(p) for p in sorted(iface.rglob("*.md")))


def assemble(component_id, repo_root, mode="cold"):
    repo_root = Path(repo_root)
    comp_dir = repo_root / "specs" / "components" / _slug(component_id)
    spec = _join([_read(comp_dir / "component.md")] + [
        _read(p) for p in sorted((comp_dir / "requirements").glob("R-*.md"))
    ])
    interface = _interface_text(comp_dir)
    constraints = _read(comp_dir / "constraints.md")
    glossary = _read(repo_root / "specs" / "glossary.md")
    digest = hashlib.sha256((spec + interface + constraints + glossary).encode("utf-8")).hexdigest()
    hint_code = None
    if mode == "hint":
        hint_code = {}
        gen_dir = repo_root / "gen" / _slug(component_id)
        if gen_dir.is_dir():
            for p in sorted(gen_dir.rglob("*.py")):
                hint_code[str(p.relative_to(gen_dir))] = _read(p)
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
    repo_root = Path(repo_root)
    comp_dir = repo_root / "specs" / "components" / _slug(component_id)
    criterion_text = _read(comp_dir / "acceptance" / (criterion_id + ".md"))
    covers = ""
    for line in criterion_text.splitlines():
        if line.startswith("Covers:"):
            covers = line[len("Covers:"):].strip()
            break
    requirement_text = _read(comp_dir / "requirements" / (covers + ".md")) if covers else ""
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=criterion_text,
        requirement_text=requirement_text,
        interface=_interface_text(comp_dir),
        glossary=_read(repo_root / "specs" / "glossary.md"),
    )
'''


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    _write(repo_root / "specs" / "product" / "labels.md", PRODUCT_MD)

    comp = repo_root / "specs" / "components" / SLUG
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / f"{REQUIREMENT_ID}.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / f"{CRITERION_ID}.md", ACCEPTANCE_MD)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)

    # The unsealed component's real candidate code.
    _write(repo_root / "gen" / SLUG / f"{MODULE_NAME}.py", CANDIDATE_SOURCE)

    # The cached generated-test for the criterion (glossary's
    # "Criterion test filename").
    _write(
        repo_root / "verification" / SLUG / "generated-test" / TEST_FILENAME,
        WEAK_TEST_SOURCE,
    )

    # Fake spec-bundle-assembler at the path verify loads it from.
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        FAKE_ASSEMBLER_SOURCE,
    )


def _fallback_test_author(bundle):
    # Only used if verify chooses to (re)author despite the cached file;
    # returns the same weak test in TestAuthoringResult's shape.
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "model": "fake-model",
        "seed": 0,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": f"verification/{SLUG}/generated-test/{TEST_FILENAME}",
            "content": WEAK_TEST_SOURCE,
        },
        "model_call_error": None,
    }


def _assert_shortfall_cited(criteria, mutation_score, overall):
    assert overall == "fail"

    # The shortfall is cited: one component-wide mutation score is reported,
    # and it is below the 0.8 bar.
    assert mutation_score is not None
    assert isinstance(mutation_score, (int, float)) and not isinstance(mutation_score, bool)
    assert mutation_score < 0.8
    # Four mutants (one per site under the four operators), one killed.
    assert mutation_score == pytest.approx(0.25)

    entries = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(entries) == 1
    entry = entries[0]
    assert field(entry, "kind") == "generated-test"
    # The weak test passes against the unmutated candidate; if an
    # implementation chooses to mark the criterion failed, the failure must
    # be the mutation-score shortfall, not the test itself.
    result = field(entry, "result")
    assert result in ("pass", "fail")
    if result == "fail":
        detail = entry.get("failure_detail") if isinstance(entry, dict) else getattr(entry, "failure_detail", None)
        assert detail is not None
        assert "mutation" in json.dumps(detail).lower()


def test_mutation_score_below_bar_fails_overall_verdict(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=_fallback_test_author
    )

    _assert_shortfall_cited(
        field(report, "criteria"),
        field(report, "mutation_score"),
        field(report, "overall"),
    )

    # The JSON form carries the same single, component-wide score.
    as_dict = report.to_dict() if hasattr(report, "to_dict") else report
    assert as_dict["overall"] == "fail"
    assert as_dict["mutation_score"] == pytest.approx(field(report, "mutation_score"))


def test_cli_exits_one_and_reports_shortfall(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    try:
        code = verifier_orchestrator.main(
            [COMPONENT_ID, f"--repo-root={repo_root}", "--format=json"]
        )
    except SystemExit as exc:
        code = exc.code

    out = capsys.readouterr().out
    assert code == 1

    payload = json.loads(out)
    _assert_shortfall_cited(
        payload["criteria"], payload["mutation_score"], payload["overall"]
    )