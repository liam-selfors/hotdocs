import sys
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = (
    "# Glossary\n"
    "\n"
    "- **Widget** — a test term.\n"
)

PRODUCT = (
    "---\n"
    "id: P-WIDGET\n"
    "title: Widget comparisons\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Widget comparisons\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Lets a caller compare and combine numbers.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: comparing two numbers.\n"
    "\n"
    "## Capability scenarios\n"
    "\n"
    "### CS-WIDGET-001\n"
    "\n"
    "Covers: P-WIDGET\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given two numbers 1 and 2\n"
    "When g is called with them\n"
    "Then it returns true\n"
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
    "Widget compares and combines numbers.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: g, h, m and do_the_thing.\n"
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
    "**R-WIDGET-001** — `g(a, b)` MUST return `a < b`.\n"
)

ACCEPTANCE = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given a = 1 and b = 2\n"
    "When g(a, b) is called\n"
    "Then it returns true\n"
    "```\n"
)

LIBRARY = (
    "# Library\n"
    "\n"
    "```\n"
    "g(a, b) -> bool\n"
    "h(a, b) -> int\n"
    "m(k, d) -> bool\n"
    "do_the_thing(x) -> object\n"
    "```\n"
)

CONSTRAINTS = (
    "# Constraints\n"
    "\n"
    "None.\n"
)

MODULE = (
    "def g(a, b):\n"
    "    return a < b\n"
    "\n"
    "\n"
    "def h(a, b):\n"
    "    return a // b\n"
    "\n"
    "\n"
    "def m(k, d):\n"
    "    return k in d\n"
    "\n"
    "\n"
    "def do_the_thing(x):\n"
    "    return x\n"
)

CACHED_TEST = (
    "import sys\n"
    "from pathlib import Path\n"
    "\n"
    "try:\n"
    "    import widget\n"
    "except ImportError:\n"
    "    sys.path.append(str(Path(__file__).resolve().parents[3] / \"gen\" / \"widget\"))\n"
    "    import widget\n"
    "\n"
    "\n"
    "def test_g_less_than():\n"
    "    assert widget.g(1, 2) is True\n"
)


def _build_fixture(repo_root: Path) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "widget-compare.md", PRODUCT)
    comp = repo_root / "specs" / "components" / "widget"
    _write(comp / "component.md", COMPONENT)
    _write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT)
    _write(comp / "acceptance" / "AC-WIDGET-001.md", ACCEPTANCE)
    _write(comp / "interface" / "library.md", LIBRARY)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(repo_root / "gen" / "widget" / "widget.py", MODULE)
    _write(
        repo_root / "verification" / "widget" / "generated-test" / "test_ac_widget_001.py",
        CACHED_TEST,
    )


def test_mutation_score_is_one_third_three_sites_one_killed(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = verifier_orchestrator.verify("comp-widget", repo_root)

    score = field(report, "mutation_score")
    assert score is not None, "unsealed component must report a mutation score"
    assert abs(float(score) - (1 / 3)) < 1e-9, (
        f"expected mutation_score of exactly 1/3 (three sites, one killed), got {score!r}"
    )