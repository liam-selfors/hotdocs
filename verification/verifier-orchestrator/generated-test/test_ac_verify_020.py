# hotdocs-criterion: sha256:3e83ec43a60ed7b3e53440f88b51a5916955bfa0d7da1060325b7471fdc923bc
import hashlib
from pathlib import Path

import pytest

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_ID = "comp-widget"
SLUG = "widget"
MODULE = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"

CRITERION_TEXT = (
    "Given a pair of numbers a and b\n"
    "When g(a, b) is called\n"
    "Then it returns whether a is less than b"
)
REQUIREMENT_TEXT = (
    "**R-WIDGET-001** — `g(a, b)` MUST return whether `a` is less than `b`."
)

MODULE_SOURCE = (
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

TEST_BODY = (
    "import " + MODULE + "\n"
    "\n"
    "\n"
    "def test_g_orders_pair():\n"
    "    assert " + MODULE + ".g(1, 2) is True\n"
    "    assert " + MODULE + ".g(2, 1) is False\n"
)


def header_line():
    digest = hashlib.sha256(
        (CRITERION_TEXT + "\n" + REQUIREMENT_TEXT).encode("utf-8")
    ).hexdigest()
    return "# hotdocs-criterion: sha256:" + digest


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "P-WIDGET.md",
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
        "Widgets compare things.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: comparing.\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it compares\n"
        "Then it answers\n"
        "```\n",
    )
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
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
        "Widget compares and divides numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: comparing.\n"
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
    write(
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "# " + REQUIREMENT_ID + "\n\n" + REQUIREMENT_TEXT + "\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n" + CRITERION_TEXT + "\n```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "g(a, b) -> bool\n"
        "h(a, b) -> int\n"
        "m(k, d) -> bool\n"
        "do_the_thing(x) -> object\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # The component's real code: three mutation sites, one function with none.
    write(repo_root / "gen" / SLUG / (MODULE + ".py"), MODULE_SOURCE)

    # Fake spec-bundle-assembler with known criterion/requirement text.
    assembler_source = (
        "CRITERION_TEXT = " + repr(CRITERION_TEXT) + "\n"
        "REQUIREMENT_TEXT = " + repr(REQUIREMENT_TEXT) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(REQUIREMENT_ID) + ",\n"
        "        'criterion_text': CRITERION_TEXT,\n"
        "        'requirement_text': REQUIREMENT_TEXT,\n"
        "        'interface': " + repr("g(a, b) -> bool\nh(a, b) -> int\nm(k, d) -> bool\ndo_the_thing(x) -> object") + ",\n"
        "        'glossary': " + repr("- **Widget** — a test term.") + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )

    # The one cached generated-test file, with a correct header.
    test_name = "test_" + CRITERION_ID.lower().replace("-", "_") + ".py"
    write(
        repo_root / "verification" / SLUG / "generated-test" / test_name,
        header_line() + "\n" + TEST_BODY,
    )


def test_mutation_score_is_one_third_with_three_sites_one_killed(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    log_path = tmp_path / "test_author_calls.log"

    def stand_in_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": header_line() + "\n" + TEST_BODY,
            },
        }

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, judge=None, test_author=stand_in_author
    )

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1
    assert field(matching[0], "result") == "pass"

    assert field(report, "mutation_error") is None
    score = field(report, "mutation_score")
    assert score is not None
    assert score == pytest.approx(1 / 3, abs=1e-9)