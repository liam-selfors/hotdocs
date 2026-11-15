import dataclasses
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


FAKE_ASSEMBLER = '''import dataclasses
import hashlib
from pathlib import Path


class _MappingMixin:
    def __getitem__(self, key):
        if key in self.__dataclass_fields__:
            return getattr(self, key)
        raise KeyError(key)

    def get(self, key, default=None):
        if key in self.__dataclass_fields__:
            return getattr(self, key)
        return default

    def keys(self):
        return list(self.__dataclass_fields__)

    def __contains__(self, key):
        return key in self.__dataclass_fields__


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


def _strip_frontmatter(text):
    if text.startswith("---\\n"):
        end = text.find("\\n---\\n", 4)
        if end != -1:
            return text[end + 5:]
    return text


def _join(texts):
    parts = [t.strip() for t in texts]
    return "\\n\\n".join(p for p in parts if p)


def _read_all(directory):
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return [p.read_text(encoding="utf-8") for p in sorted(directory.rglob("*.md"))]


def assemble(component_id, repo_root, mode="cold"):
    root = Path(repo_root)
    comp = root / "specs" / "components" / _slug(component_id)
    spec = _join([_strip_frontmatter((comp / "component.md").read_text(encoding="utf-8"))]
                 + _read_all(comp / "requirements"))
    interface = _join(_read_all(comp / "interface"))
    constraints_path = comp / "constraints.md"
    constraints = _join([constraints_path.read_text(encoding="utf-8")]) if constraints_path.is_file() else ""
    glossary_path = root / "specs" / "glossary.md"
    glossary = _join([glossary_path.read_text(encoding="utf-8")]) if glossary_path.is_file() else ""
    digest = hashlib.sha256("\\0".join([spec, interface, constraints, glossary]).encode("utf-8")).hexdigest()
    hint_code = None
    if mode == "hint":
        gen_dir = root / "gen" / _slug(component_id)
        hint_code = {}
        if gen_dir.is_dir():
            for p in sorted(gen_dir.rglob("*.py")):
                hint_code[str(p.relative_to(gen_dir))] = p.read_text(encoding="utf-8")
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
    root = Path(repo_root)
    comp = root / "specs" / "components" / _slug(component_id)
    text = (comp / "acceptance" / (criterion_id + ".md")).read_text(encoding="utf-8")
    covers = ""
    for line in text.splitlines():
        if line.startswith("Covers:"):
            covers = line[len("Covers:"):].strip()
            break
    req_path = comp / "requirements" / (covers + ".md")
    requirement_text = req_path.read_text(encoding="utf-8").strip() if req_path.is_file() else ""
    glossary_path = root / "specs" / "glossary.md"
    glossary = _join([glossary_path.read_text(encoding="utf-8")]) if glossary_path.is_file() else ""
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=text.strip(),
        requirement_text=requirement_text,
        interface=_join(_read_all(comp / "interface")),
        glossary=glossary,
    )
'''


def _build_fixture(root):
    _write(root, "specs/glossary.md", "# Glossary\n\n- **Widget** — a test term.\n")

    _write(
        root,
        "specs/product/widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provides tripled numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: tripling numbers.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the assembled widget system\n"
        "When a number is tripled\n"
        "Then the tripled number is produced\n"
        "```\n",
    )

    comp = "specs/components/widget/"
    _write(
        root,
        comp + "component.md",
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
        "Widget triples a number.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: tripling integers.\n"
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
        "- Initial draft.\n",
    )
    _write(
        root,
        comp + "requirements/R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — `triple(x)` MUST return a `Tripled` whose `value` is `3 * x`.\n",
    )
    _write(
        root,
        comp + "requirements/R-WIDGET-002.md",
        "# R-WIDGET-002\n\n**R-WIDGET-002** — `triple(x)` MUST accept a negative `x`.\n",
    )
    _write(
        root,
        comp + "requirements/R-WIDGET-003.md",
        "# R-WIDGET-003\n\n**R-WIDGET-003** — The interface of `triple` MUST be unambiguous.\n",
    )
    _write(
        root,
        comp + "interface/library.md",
        "# Library\n\n```\ntriple(x: int) -> Tripled\n```\n",
    )
    _write(
        root,
        comp + "interface/data/Tripled.md",
        "# `Tripled`\n\n```json\n{ \"value\": 6 }\n```\n",
    )
    _write(root, comp + "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        root,
        comp + "acceptance/AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a n is 2\n"
        "When triple is invoked with [n]\n"
        "Then value equals 6\n"
        "```\n",
    )
    _write(
        root,
        comp + "acceptance/AC-WIDGET-002.md",
        "# AC-WIDGET-002\n"
        "\n"
        "Covers: R-WIDGET-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a negative number such as -2\n"
        "When triple is called with it\n"
        "Then the returned value is -6\n"
        "```\n",
    )
    _write(
        root,
        comp + "acceptance/AC-WIDGET-003.md",
        "# AC-WIDGET-003\n"
        "\n"
        "Covers: R-WIDGET-003\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the widget interface documentation\n"
        "When a reviewer reads it\n"
        "Then the behavior of triple is unambiguous\n"
        "```\n",
    )

    # The component's own generated code.
    _write(
        root,
        "gen/widget/widget.py",
        "from dataclasses import dataclass\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class Tripled:\n"
        "    value: int\n"
        "\n"
        "\n"
        "def triple(x):\n"
        "    return Tripled(value=3 * x)\n",
    )

    # A cached generated test, so no test_author is needed.
    _write(
        root,
        "verification/widget/generated-test/test_ac_widget_002.py",
        "import widget\n"
        "\n"
        "\n"
        "def test_ac_widget_002():\n"
        "    assert widget.triple(-2).value == -6\n",
    )

    # Fake spec-bundle-assembler planted where verify loads it from.
    _write(root, "gen/spec-bundle-assembler/spec_bundle_assembler.py", FAKE_ASSEMBLER)


def _as_dict(report):
    if isinstance(report, dict):
        return report
    return report.to_dict()


def _consistent_judge(bundle):
    return {"result": "pass", "rationale": "The criterion is satisfied."}


def test_ac_verify_008_verify_is_idempotent(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)
    monkeypatch.chdir(repo_root)

    first = verifier_orchestrator.verify("comp-widget", repo_root, judge=_consistent_judge)
    second = verifier_orchestrator.verify("comp-widget", repo_root, judge=_consistent_judge)

    d1 = _as_dict(first)
    d2 = _as_dict(second)

    # Non-trivial run: every fixture criterion is reported.
    ids1 = sorted(field(c, "id") for c in field(first, "criteria"))
    assert ids1 == ["AC-WIDGET-001", "AC-WIDGET-002", "AC-WIDGET-003"]

    # Then: the two VerificationReports are identical.
    assert json.dumps(d1, sort_keys=True, default=str) == json.dumps(d2, sort_keys=True, default=str)
    assert d1 == d2
    assert field(first, "component_id") == field(second, "component_id")
    assert field(first, "criteria") == field(second, "criteria")
    assert field(first, "requirement_results") == field(second, "requirement_results")
    assert field(first, "interface_drift") == field(second, "interface_drift")
    assert field(first, "mutation_score") == field(second, "mutation_score")
    assert field(first, "overall") == field(second, "overall")
    if dataclasses.is_dataclass(first) and dataclasses.is_dataclass(second):
        assert first == second