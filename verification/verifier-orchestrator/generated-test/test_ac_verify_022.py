# hotdocs-criterion: sha256:2d59e9348c0b482249a23b48792ed456994bc1a5de77100f2f9087fb94a2bf2d
import hashlib
from pathlib import Path

import verifier_orchestrator


SLUG = "widget"
COMPONENT_ID = "comp-widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"

CRITERION_TEXT = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When triple(x) is called\n"
    "Then it returns 6\n"
    "```\n"
)

REQUIREMENT_TEXT = (
    "# R-WIDGET-001\n"
    "\n"
    "**R-WIDGET-001** \u2014 `triple(x)` MUST return `3 * x`.\n"
)

INTERFACE_TEXT = "# Library\n\n```\ntriple(x: int) -> int\n```\n"

GLOSSARY_TEXT = "# Glossary\n\n- **Widget** \u2014 a test term.\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def header_line():
    digest = hashlib.sha256(
        (CRITERION_TEXT + "\n" + REQUIREMENT_TEXT).encode("utf-8")
    ).hexdigest()
    return "# hotdocs-criterion: sha256:" + digest


def generated_test_body():
    return (
        header_line() + "\n"
        "import widget\n"
        "\n"
        "\n"
        "def test_triple_values():\n"
        "    assert widget.triple(2) == 6\n"
        "    assert widget.triple(7) == 21\n"
        "    assert widget.triple(-1) == -3\n"
        "    assert widget.triple(0) == 0\n"
        "    assert widget.triple(1) == 3\n"
        "    assert type(widget.triple(4)) is int\n"
    )


def build_fixture(repo_root):
    write(repo_root / "specs" / "glossary.md", GLOSSARY_TEXT)

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
        "Triple numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: tripling.\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When triple(x) is called\n"
        "Then it returns 6\n"
        "```\n",
    )

    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
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
        "- In scope: tripling.\n"
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
    write(comp / "requirements" / (REQUIREMENT_ID + ".md"), REQUIREMENT_TEXT)
    write(comp / "acceptance" / (CRITERION_ID + ".md"), CRITERION_TEXT)
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # The component's real code: one function.
    gen_dir = repo_root / "gen" / SLUG
    write(
        gen_dir / "widget.py",
        "def triple(x):\n"
        "    return x * 3\n",
    )

    # Stand-in spec-bundle-assembler.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "CRITERION_TEXT = " + repr(CRITERION_TEXT) + "\n"
        "REQUIREMENT_TEXT = " + repr(REQUIREMENT_TEXT) + "\n"
        "INTERFACE_TEXT = " + repr(INTERFACE_TEXT) + "\n"
        "GLOSSARY_TEXT = " + repr(GLOSSARY_TEXT) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(REQUIREMENT_ID) + ",\n"
        "        'criterion_text': CRITERION_TEXT,\n"
        "        'requirement_text': REQUIREMENT_TEXT,\n"
        "        'interface': INTERFACE_TEXT,\n"
        "        'glossary': GLOSSARY_TEXT,\n"
        "        'dependency_interfaces': {},\n"
        "    }\n",
    )

    # conftest.py that puts the ABSOLUTE gen/<slug>/ path first on
    # sys.path and imports the module from there.
    write(
        repo_root / "verification" / SLUG / "conftest.py",
        "import sys\n"
        "sys.path.insert(0, " + repr(str(gen_dir.resolve())) + ")\n"
        "import widget\n",
    )

    # Cached generated test with a correct header.
    write(
        repo_root
        / "verification"
        / SLUG
        / "generated-test"
        / "test_ac_widget_001.py",
        generated_test_body(),
    )


def test_conftest_pinning_original_module_does_not_hide_mutants(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    log_path = tmp_path / "test_author_calls.log"

    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": generated_test_body(),
            },
            "model_call_error": None,
        }

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, judge=None, test_author=test_author
    )

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1, criteria
    assert field(matching[0], "result") == "pass", matching[0]

    assert field(report, "mutation_error") is None, field(report, "mutation_error")
    assert field(report, "mutation_score") == 1.0, field(report, "mutation_score")