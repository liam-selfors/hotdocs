# hotdocs-criterion: sha256:acabc539e4ecfade4e5923f05033b1aef308c105d6cb58abca75af0ba41b32d9
import sys
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


MODULE_SOURCE = (
    "def scale(a: int, b: int) -> int:\n"
    "    return a * b + a\n"
    "\n"
    "\n"
    "def pick(x: int, y: int) -> bool:\n"
    "    if x > y and x != 0:\n"
    "        return True\n"
    "    return False\n"
)

TEST_SCALE_SOURCE = (
    "import widget\n"
    "\n"
    "\n"
    "def test_scale_values():\n"
    "    assert widget.scale(3, 4) == 15\n"
    "    assert widget.scale(2, 5) == 12\n"
)

TEST_PICK_SOURCE = (
    "import widget\n"
    "\n"
    "\n"
    "def test_pick_values():\n"
    "    assert widget.pick(3, 2) is True\n"
    "    assert widget.pick(1, 2) is False\n"
    "    assert widget.pick(0, -1) is False\n"
)

REQ_001_TEXT = "# R-WIDGET-001\n\n**R-WIDGET-001** \u2014 `scale(a, b)` MUST return `a * b + a`.\n"
REQ_002_TEXT = (
    "# R-WIDGET-002\n\n**R-WIDGET-002** \u2014 `pick(x, y)` MUST return `True` exactly "
    "when `x > y` and `x` is not zero, else `False`.\n"
)

AC_001_TEXT = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given a and b are 3 and 4\n"
    "When scale is called with them\n"
    "Then it returns 15\n"
    "```\n"
)

AC_002_TEXT = (
    "# AC-WIDGET-002\n"
    "\n"
    "Covers: R-WIDGET-002\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x is 3 and y is 2\n"
    "When pick is called with them\n"
    "Then it returns True\n"
    "```\n"
)

LIBRARY_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "scale(a: int, b: int) -> int\n"
    "pick(x: int, y: int) -> bool\n"
    "```\n"
)


def build_fixture(repo_root, log_path):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** \u2014 a test term.\n")
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets compute things.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widgets.\n",
    )
    comp = repo_root / "specs" / "components" / "widget"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-WIDGET]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget scales numbers and picks between them.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: scale and pick.\n"
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
        "- Initial.\n",
    )
    write(comp / "requirements" / "R-WIDGET-001.md", REQ_001_TEXT)
    write(comp / "requirements" / "R-WIDGET-002.md", REQ_002_TEXT)
    write(comp / "acceptance" / "AC-WIDGET-001.md", AC_001_TEXT)
    write(comp / "acceptance" / "AC-WIDGET-002.md", AC_002_TEXT)
    write(comp / "interface" / "library.md", LIBRARY_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(repo_root / "gen" / "widget" / "widget.py", MODULE_SOURCE)

    assembler_source = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "COVERS = " + repr({"AC-WIDGET-001": "R-WIDGET-001", "AC-WIDGET-002": "R-WIDGET-002"}) + "\n"
        "CRITERIA = " + repr({"AC-WIDGET-001": AC_001_TEXT, "AC-WIDGET-002": AC_002_TEXT}) + "\n"
        "REQS = " + repr({"R-WIDGET-001": REQ_001_TEXT, "R-WIDGET-002": REQ_002_TEXT}) + "\n"
        "INTERFACE = " + repr(LIBRARY_TEXT) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('assemble ' + str(criterion_id) + '\\n')\n"
        "    covers = COVERS[criterion_id]\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': covers,\n"
        "        'criterion_text': CRITERIA[criterion_id],\n"
        "        'requirement_text': REQS[covers],\n"
        "        'interface': INTERFACE,\n"
        "        'glossary': '# Glossary',\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )


def test_mutation_score_is_union_of_all_generated_tests(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    build_fixture(repo_root, log_path)

    sources = {"AC-WIDGET-001": TEST_SCALE_SOURCE, "AC-WIDGET-002": TEST_PICK_SOURCE}

    def author(bundle):
        criterion_id = field(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("author " + str(criterion_id) + "\n")
        name = "test_" + criterion_id.lower().replace("-", "_") + ".py"
        return {
            "component_id": field(bundle, "component_id"),
            "criterion_id": criterion_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/widget/generated-test/" + name,
                "content": sources[criterion_id],
            },
        }

    report = verifier_orchestrator.verify("comp-widget", repo_root, test_author=author)

    logged = log_path.read_text(encoding="utf-8").splitlines()
    assert "author AC-WIDGET-001" in logged
    assert "author AC-WIDGET-002" in logged

    criteria = field(report, "criteria")
    by_id = {field(c, "id"): c for c in criteria}
    assert field(by_id["AC-WIDGET-001"], "result") == "pass"
    assert field(by_id["AC-WIDGET-002"], "result") == "pass"

    assert field(report, "mutation_error") is None
    score = field(report, "mutation_score")
    assert score is not None

    # 7 mutants total: scale has 2 sites (*, +), pick has 5 (>, and, !=, True, False).
    # The scale test alone kills 2/7, the pick test alone 5/7; their average is 0.5.
    # Only the union of both tests kills all 7.
    isolated_scale = 2 / 7
    isolated_pick = 5 / 7
    assert score > isolated_pick
    assert score > isolated_scale
    assert score > (isolated_scale + isolated_pick) / 2
    assert score >= 0.8
    assert abs(score - 1.0) < 1e-9

    assert field(report, "overall") == "pass"