"""AC-VERIFY-012 (Covers: R-VERIFY-003).

Given a component with one llm-judge-kind acceptance criterion and a mock
judge callable that records how many times it was called,
When verify runs with that judge configured,
Then the mock judge was called exactly once for that criterion: never
zero times (it was configured) and never more than once (no
disagreement-style second call).
"""

import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Widget** — a test term.\n"

CAPABILITY = (
    "---\n"
    "id: P-WIDGET\n"
    "title: Widget Capability\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Widget Capability\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Widgets double numbers.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: doubling.\n"
    "\n"
    "## Capability scenarios\n"
    "\n"
    "### CS-WIDGET-001\n"
    "\n"
    "Covers: P-WIDGET\n"
    "Kind: llm-judge\n"
    "\n"
    "```gherkin\n"
    "Given a widget system\n"
    "When a number is doubled\n"
    "Then the doubled number is returned\n"
    "```\n"
)

COMPONENT = (
    "---\n"
    "id: comp-widget\n"
    "title: Widget\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "realizes: [P-WIDGET]\n"
    "---\n"
    "\n"
    "# Widget\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Widget doubles a number.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: doubling a number.\n"
    "- Out of scope: everything else.\n"
    "\n"
    "## Definitions\n"
    "\n"
    "None.\n"
    "\n"
    "## Behavior\n"
    "\n"
    "See `requirements/`.\n"
    "\n"
    "## Interfaces\n"
    "\n"
    "See `interface/`.\n"
    "\n"
    "## Data\n"
    "\n"
    "See `interface/data/`.\n"
    "\n"
    "## Acceptance criteria\n"
    "\n"
    "See `acceptance/`.\n"
    "\n"
    "## Non-functional constraints\n"
    "\n"
    "See `constraints.md`.\n"
    "\n"
    "## Open questions\n"
    "\n"
    "## Change log\n"
    "\n"
    "- Initial draft.\n"
)

REQUIREMENT = (
    "# R-WIDGET-001\n"
    "\n"
    "**R-WIDGET-001** — The widget's documentation MUST describe "
    "`double_it(x)` clearly and without contradiction.\n"
)

ACCEPTANCE = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: llm-judge\n"
    "\n"
    "```gherkin\n"
    "Given the widget component's specification\n"
    "When a reviewer reads its description of double_it\n"
    "Then the description is clear and free of contradiction\n"
    "```\n"
)

LIBRARY = "# Library\n\n```\ndouble_it(x: int) -> int\n```\n"

CONSTRAINTS = "# Constraints\n\nNone.\n"

GEN_WIDGET = "def double_it(x):\n    return 2 * x\n"

FAKE_ASSEMBLER = '''\
import dataclasses
from dataclasses import dataclass, field as dc_field
from pathlib import Path


class _MappingMixin:
    def _names(self):
        return [f.name for f in dataclasses.fields(self)]

    def __getitem__(self, key):
        if key in self._names():
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        if key in self._names():
            return getattr(self, key)
        return default

    def keys(self):
        return list(self._names())

    def items(self):
        return [(n, getattr(self, n)) for n in self._names()]

    def values(self):
        return [getattr(self, n) for n in self._names()]

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())

    def __contains__(self, key):
        return key in self._names()


@dataclass
class SpecBundle(_MappingMixin):
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dc_field(default_factory=dict)
    dependency_context: dict = dc_field(default_factory=dict)
    dependency_usage: dict = dc_field(default_factory=dict)
    vars: dict = dc_field(default_factory=dict)
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
    dependency_interfaces: dict = dc_field(default_factory=dict)


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def _interface_text(comp_dir):
    parts = []
    idir = comp_dir / "interface"
    if idir.is_dir():
        for p in sorted(idir.rglob("*.md")):
            t = _read(p).strip()
            if t:
                parts.append(t)
    return "\\n\\n".join(parts)


def assemble(component_id, repo_root, mode="cold"):
    repo_root = Path(repo_root)
    comp_dir = repo_root / "specs" / "components" / _slug(component_id)
    spec_parts = [_read(comp_dir / "component.md").strip()]
    rdir = comp_dir / "requirements"
    if rdir.is_dir():
        for p in sorted(rdir.glob("R-*.md")):
            spec_parts.append(_read(p).strip())
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "0" * 64,
        spec="\\n\\n".join(x for x in spec_parts if x),
        interface=_interface_text(comp_dir),
        constraints=_read(comp_dir / "constraints.md").strip(),
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary=_read(repo_root / "specs" / "glossary.md").strip(),
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    repo_root = Path(repo_root)
    comp_dir = repo_root / "specs" / "components" / _slug(component_id)
    ac_text = _read(comp_dir / "acceptance" / (criterion_id + ".md"))
    covers = ""
    for line in ac_text.splitlines():
        if line.startswith("Covers:"):
            covers = line[len("Covers:"):].strip()
            break
    criterion_text = ""
    if "```gherkin" in ac_text:
        after = ac_text.split("```gherkin", 1)[1]
        criterion_text = after.split("```", 1)[0].strip()
    requirement_text = _read(comp_dir / "requirements" / (covers + ".md")).strip() if covers else ""
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=criterion_text,
        requirement_text=requirement_text,
        interface=_interface_text(comp_dir),
        glossary=_read(repo_root / "specs" / "glossary.md").strip(),
        dependency_interfaces={},
    )
'''


def _build_fixture(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "widget-capability.md", CAPABILITY)
    comp = repo_root / "specs" / "components" / "widget"
    _write(comp / "component.md", COMPONENT)
    _write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT)
    _write(comp / "acceptance" / "AC-WIDGET-001.md", ACCEPTANCE)
    _write(comp / "interface" / "library.md", LIBRARY)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(repo_root / "gen" / "widget" / "widget.py", GEN_WIDGET)
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        FAKE_ASSEMBLER,
    )


def test_llm_judge_called_exactly_once_for_the_criterion(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    log_path = tmp_path / "judge_calls.log"

    def recording_judge(bundle):
        try:
            criterion_id = field(bundle, "criterion_id")
        except (KeyError, AttributeError, TypeError):
            criterion_id = "<unknown>"
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"criterion_id": criterion_id}) + "\n")
        return {"result": "pass", "rationale": "Clear and consistent."}

    report = verifier_orchestrator.verify(
        "comp-widget", repo_root, judge=recording_judge
    )
    assert report is not None

    calls = []
    if log_path.exists():
        calls = [
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    # Never zero times: the judge was configured.
    assert len(calls) != 0, "configured judge was never called"
    # Never more than once: no disagreement-style second call.
    assert len(calls) == 1, f"judge called {len(calls)} times, expected exactly 1"
    # And that single call was for the one llm-judge criterion.
    assert calls[0]["criterion_id"] == "AC-WIDGET-001"