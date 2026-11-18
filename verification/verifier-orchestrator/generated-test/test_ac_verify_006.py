# hotdocs-criterion: sha256:8fba48c44d57791db097e09179c4d5ee8098d5fa940810f29bba1909135281cd
import json
import sys
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


CRITERION_TEXT = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given a number 2\n"
    "When double is called with it\n"
    "Then it returns 4\n"
    "```\n"
)

REQUIREMENT_TEXT = (
    "# R-WIDGET-001\n"
    "\n"
    "**R-WIDGET-001** \u2014 `double(x)` MUST return `2 * x`.\n"
)

INTERFACE_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "double(x: int) -> int\n"
    "is_big(x: int) -> bool\n"
    "flag() -> bool\n"
    "```\n"
)

GLOSSARY_TEXT = (
    "# Glossary\n"
    "\n"
    "- **Widget** \u2014 a test term.\n"
)

# Three mutation sites: `*` (killed by the test), `>` and `True`
# (both survive), so the score is 1/3, well below the 0.8 bar.
MODULE_SOURCE = (
    "def double(x: int) -> int:\n"
    "    return x * 2\n"
    "\n"
    "\n"
    "def is_big(x: int) -> bool:\n"
    "    return x > 10\n"
    "\n"
    "\n"
    "def flag() -> bool:\n"
    "    return True\n"
)

GENERATED_TEST_SOURCE = (
    "import widget\n"
    "\n"
    "\n"
    "def test_double_two():\n"
    "    assert widget.double(2) == 4\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, assembler_log):
    write(repo_root / "specs" / "glossary.md", GLOSSARY_TEXT)

    write(
        repo_root / "specs" / "product" / "widget.md",
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
        "- In scope: doubling.\n",
    )

    comp_dir = repo_root / "specs" / "components" / SLUG
    write(
        comp_dir / "component.md",
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
        "Widget doubles a number.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
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
    write(comp_dir / "requirements" / (REQUIREMENT_ID + ".md"), REQUIREMENT_TEXT)
    write(comp_dir / "acceptance" / (CRITERION_ID + ".md"), CRITERION_TEXT)
    write(comp_dir / "interface" / "library.md", INTERFACE_TEXT)
    write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")

    write(repo_root / "gen" / SLUG / "widget.py", MODULE_SOURCE)

    bundle = {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQUIREMENT_ID,
        "criterion_text": CRITERION_TEXT,
        "requirement_text": REQUIREMENT_TEXT,
        "interface": INTERFACE_TEXT,
        "glossary": GLOSSARY_TEXT,
        "dependency_interfaces": {},
    }
    assembler_source = (
        "import json\n"
        "\n"
        "_BUNDLE = json.loads(" + repr(json.dumps(bundle)) + ")\n"
        "_LOG = " + repr(str(assembler_log)) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(str(component_id) + ' ' + str(criterion_id) + '\\n')\n"
        "    result = dict(_BUNDLE)\n"
        "    result['component_id'] = component_id\n"
        "    result['criterion_id'] = criterion_id\n"
        "    return result\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )


def make_author_stub(author_log):
    def author_stub(bundle):
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write("call\n")
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
                "content": GENERATED_TEST_SOURCE,
            },
        }

    return author_stub


def test_mutation_score_below_bar_fails_overall(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    assembler_log = logs / "assembler.log"
    author_log = logs / "author.log"

    build_fixture(repo_root, assembler_log)

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_author_stub(author_log)
    )

    # The fakes actually ran.
    assert author_log.is_file()
    assert len(author_log.read_text(encoding="utf-8").splitlines()) >= 1
    assert assembler_log.is_file()

    criteria = field(report, "criteria")
    entries = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(entries) == 1
    entry = entries[0]
    assert field(entry, "kind") == "generated-test"
    # The test passes on the real code; the mutation score affects only overall.
    assert field(entry, "result") == "pass"

    # The baseline passed, so a score was computed and no mutation error set.
    assert field(report, "mutation_error") is None
    score = field(report, "mutation_score")
    assert score is not None
    assert isinstance(score, (int, float))
    assert 0.0 <= score < 0.8

    # Overall verdict is fail because of the shortfall.
    assert field(report, "overall") == "fail"

    # The JSON form cites the same shortfall.
    as_dict = report.to_dict()
    assert as_dict["overall"] == "fail"
    assert as_dict["mutation_score"] is not None
    assert as_dict["mutation_score"] < 0.8
    assert as_dict["mutation_error"] is None