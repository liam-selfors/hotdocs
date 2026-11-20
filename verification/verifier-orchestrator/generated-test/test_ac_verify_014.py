# hotdocs-criterion: sha256:9e63b4100800dcd25594994653799b91ff474963cde0882bd6a87be9b016e562
# AC-VERIFY-014: two repo_roots with a same-slug component, verified in turn in
# one process, each get results reflecting their own code (R-VERIFY-013).
import shutil
from pathlib import Path

import verifier_orchestrator


SLUG = "widget"
COMPONENT_ID = "comp-widget"
CRITERION_ID = "AC-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def live_root():
    return (
        Path(verifier_orchestrator.__file__).resolve().parents[1]
        / "spec-bundle-assembler"
    ).resolve().parents[1]


CODE_A = (
    "from types import SimpleNamespace\n"
    "\n"
    "\n"
    "def get_info(x):\n"
    "    return SimpleNamespace(value=x + 1)\n"
    "\n"
    "\n"
    "def extra_name(y):\n"
    "    return y\n"
)

CODE_B = (
    "from types import SimpleNamespace\n"
    "\n"
    "\n"
    "def get_info(x):\n"
    "    return SimpleNamespace(value=x + 100)\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "get_info(x: int) -> Info\n"
    "extra_name(y: int) -> int\n"
    "```\n"
    "\n"
    "`get_info` returns an object whose `value` attribute is `x + 1`.\n"
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
    "Computes widget information.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: get_info.\n"
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
    "Widgets.\n"
)

REQUIREMENT_MD = (
    "# R-WIDGET-001\n"
    "\n"
    "**R-WIDGET-001** - `get_info(x)` MUST return an object whose `value`\n"
    "is `x + 1`.\n"
)

ACCEPTANCE_MD = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given a n is 1\n"
    "When get_info is invoked with {\"x\": n}\n"
    "Then value equals 2\n"
    "```\n"
)

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

ASSEMBLER_SRC = (
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': 'R-WIDGET-001',\n"
    "        'criterion_text': 'criterion',\n"
    "        'requirement_text': 'requirement',\n"
    "        'interface': 'interface',\n"
    "        'glossary': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'testing': '',\n"
    "    }\n"
)

PROBE_SRC = (
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


def build_fixture(repo_root, code):
    comp = repo_root / "specs" / "components" / SLUG
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT_MD)
    write(comp / "acceptance" / "AC-WIDGET-001.md", ACCEPTANCE_MD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "constraints.md", CONSTRAINTS_MD)
    write(repo_root / "specs" / "product" / "P-WIDGET.md", PRODUCT_MD)
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")
    write(repo_root / "gen" / SLUG / "widget.py", code)
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        ASSEMBLER_SRC,
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", PROBE_SRC)
    shutil.copytree(
        live_root() / "pipeline" / "criterion-compiler",
        repo_root / "pipeline" / "criterion-compiler",
        ignore=shutil.ignore_patterns("__pycache__"),
    )


def criterion_result(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, criteria
    return field(matches[0], "result")


def test_same_slug_in_two_repo_roots_never_share_modules(tmp_path):
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    build_fixture(repo_a, CODE_A)
    build_fixture(repo_b, CODE_B)

    report_a = verifier_orchestrator.verify(COMPONENT_ID, repo_a)
    report_b = verifier_orchestrator.verify(COMPONENT_ID, repo_b)
    report_a_again = verifier_orchestrator.verify(COMPONENT_ID, repo_a)

    # repo_a's code satisfies the interface and the compiled criterion.
    assert field(report_a, "interface_drift") is False
    assert criterion_result(report_a) == "pass"

    # repo_b's code lacks a declared function and returns the wrong value:
    # its results must reflect its own code, not repo_a's cached module.
    assert field(report_b, "interface_drift") is True
    assert criterion_result(report_b) == "fail"
    assert field(report_b, "overall") == "fail"

    # Going back to repo_a must not reuse repo_b's module either.
    assert field(report_a_again, "interface_drift") is False
    assert criterion_result(report_a_again) == "pass"