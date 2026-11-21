# hotdocs-criterion: sha256:47ea5cb71758e077465b05697c5239464f00aaf3525aa66c6ab1187d4922bac2
import shutil
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


ASSEMBLER_SOURCE = (
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': 'R-WIDGET-001',\n"
    "        'criterion_text': 'criterion text',\n"
    "        'requirement_text': 'requirement text',\n"
    "        'interface': 'make_thing(x)',\n"
    "        'glossary': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'testing': '',\n"
    "    }\n"
)

PROBE_SOURCE = (
    "class _Report:\n"
    "    def __init__(self):\n"
    "        self.ok = True\n"
    "        self.findings = []\n"
    "        self.tests_run = 0\n"
    "        self.tests_reached = 0\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'ok': self.ok, 'findings': list(self.findings),\n"
    "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
    "    return _Report()\n"
)

WIDGET_SOURCE = (
    "class Thing:\n"
    "    def __init__(self, foo):\n"
    "        self.foo = foo\n"
    "\n"
    "\n"
    "def make_thing(x):\n"
    "    return Thing(3)\n"
)

COMPONENT_MD = (
    "---\n"
    "id: comp-widget\n"
    "title: Widget\n"
    "status: draft\n"
    "owners: [test-team]\n"
    "realizes: [P-WIDGET]\n"
    "---\n"
    "\n"
    "# Widget\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Makes things.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: making things.\n"
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
    "- Initial.\n"
)

PRODUCT_MD = (
    "---\n"
    "id: P-WIDGET\n"
    "title: Widget capability\n"
    "status: draft\n"
    "owners: [test-team]\n"
    "---\n"
    "\n"
    "# Widget capability\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Things get made.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- Making things.\n"
)

REQUIREMENT_MD = (
    "# R-WIDGET-001\n"
    "\n"
    "**R-WIDGET-001** - `make_thing(x)` MUST return an object whose `foo` is 5.\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "make_thing(x)\n"
    "```\n"
    "\n"
    "Returns an object with attribute `foo`.\n"
)

ACCEPTANCE_MD = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given a seed is 1\n"
    "When make_thing is invoked with {\"x\": seed}\n"
    "Then foo equals 5\n"
    "```\n"
)

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

GLOSSARY_MD = "# Glossary\n\n- **Thing** - a made thing.\n"


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "widget"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT_MD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "acceptance" / "AC-WIDGET-001.md", ACCEPTANCE_MD)
    write(comp / "constraints.md", CONSTRAINTS_MD)
    write(repo_root / "specs" / "product" / "widget.md", PRODUCT_MD)
    write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)

    write(repo_root / "gen" / "widget" / "widget.py", WIDGET_SOURCE)
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        ASSEMBLER_SOURCE,
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", PROBE_SOURCE)

    live = (
        Path(verifier_orchestrator.__file__).resolve().parents[1]
        / "spec-bundle-assembler"
    ).resolve().parents[1]
    src = live / "pipeline" / "criterion-compiler"
    dst = repo_root / "pipeline" / "criterion-compiler"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))


def test_compiled_failure_carries_expected_and_actual(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    report = verifier_orchestrator.verify("comp-widget", repo_root)

    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == "AC-WIDGET-001"]
    assert len(matches) == 1, criteria
    criterion = matches[0]

    assert field(criterion, "result") == "fail", criterion
    detail = field(criterion, "failure_detail")
    assert detail is not None, criterion

    expected = field(detail, "expected")
    actual = field(detail, "actual")
    assert expected == 5, detail
    assert type(expected) is int, detail
    assert actual == 3, detail
    assert type(actual) is int, detail
    assert isinstance(field(detail, "message"), str), detail