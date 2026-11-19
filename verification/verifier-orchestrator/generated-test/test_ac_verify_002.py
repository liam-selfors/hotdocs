# hotdocs-criterion: sha256:36189670b5334f5d814847c8b17867c5ad10e000b54a2743dba2316cdcf7dee5
import hashlib
from pathlib import Path

import pytest

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
MODULE = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQ_ID = "R-WIDGET-001"

CRITERION_TEXT = (
    "Given a number 3\n"
    "When double_it is called with it\n"
    "Then it returns 6"
)
REQUIREMENT_TEXT = "**R-WIDGET-001** — `double_it(x)` MUST return `2 * x`."


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def criterion_header():
    digest = hashlib.sha256(
        (CRITERION_TEXT + "\n" + REQUIREMENT_TEXT).encode("utf-8")
    ).hexdigest()
    return "# hotdocs-criterion: sha256:" + digest


def assembler_source():
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(REQ_ID) + ",\n"
        "        'criterion_text': " + repr(CRITERION_TEXT) + ",\n"
        "        'requirement_text': " + repr(REQUIREMENT_TEXT) + ",\n"
        "        'interface': " + repr("# Library\n\n```\ndouble_it(x: int) -> int\n```\n") + ",\n"
        "        'glossary': " + repr("# Glossary\n\n- **Widget** — a test term.\n") + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )


def cached_test_source():
    return (
        criterion_header() + "\n"
        "from pathlib import Path\n"
        "\n"
        "import " + MODULE + "\n"
        "\n"
        "\n"
        "def test_double_it():\n"
        "    here = Path(" + MODULE + ".__file__).resolve()\n"
        "    assert here.parent.name == " + repr(SLUG) + "\n"
        "    assert here.parent.parent.name == 'gen'\n"
        "    assert " + MODULE + ".double_it(3) == 6\n"
    )


def build_fixture(repo_root, implementation):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )
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
        "Numbers can be doubled.\n",
    )
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
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
    write(
        comp / "requirements" / (REQ_ID + ".md"),
        "# " + REQ_ID + "\n\n" + REQUIREMENT_TEXT + "\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble_it(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQ_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        + CRITERION_TEXT + "\n"
        "```\n",
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    write(repo_root / "gen" / SLUG / (MODULE + ".py"), implementation)
    write(
        repo_root
        / "verification"
        / SLUG
        / "generated-test"
        / ("test_" + CRITERION_ID.lower().replace("-", "_") + ".py"),
        cached_test_source(),
    )


@pytest.mark.parametrize(
    "implementation, expected",
    [
        ("def double_it(x):\n    return x * 2\n", "pass"),
        ("def double_it(x):\n    return x + 1\n", "fail"),
    ],
)
def test_cached_generated_test_is_run_against_gen_and_reported(
    tmp_path, implementation, expected
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, implementation)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1, criteria
    entry = matching[0]
    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") == expected, entry
    if expected == "fail":
        # A test ran and failed: the failure is the implementation's.
        assert field(entry, "failure_origin") == "implementation", entry