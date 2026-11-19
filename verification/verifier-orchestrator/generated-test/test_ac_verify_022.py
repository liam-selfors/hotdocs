# hotdocs-criterion: sha256:2d59e9348c0b482249a23b48792ed456994bc1a5de77100f2f9087fb94a2bf2d
import hashlib
from pathlib import Path

import verifier_orchestrator


CRITERION_TEXT = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given a number n\n"
    "When is_positive(n) is called\n"
    "Then it returns whether n is greater than zero\n"
    "```\n"
)

REQUIREMENT_TEXT = (
    "# R-WIDGET-001\n"
    "\n"
    "**R-WIDGET-001** \u2014 `is_positive(n)` MUST return `True` exactly when `n > 0`.\n"
)

MODULE_SOURCE = (
    "def is_positive(n):\n"
    "    return n > 0\n"
)

TEST_BODY = (
    "import widget\n"
    "\n"
    "\n"
    "def test_is_positive():\n"
    "    assert widget.is_positive(5) is True\n"
    "    assert widget.is_positive(-3) is False\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def header_line():
    digest = hashlib.sha256(
        (CRITERION_TEXT + "\n" + REQUIREMENT_TEXT).encode("utf-8")
    ).hexdigest()
    return "# hotdocs-criterion: sha256:" + digest + "\n"


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** \u2014 a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "widget.md",
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
        "Classify numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: positivity.\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given a number\n"
        "When it is classified\n"
        "Then its sign is known\n"
        "```\n",
    )
    comp = repo_root / "specs" / "components" / "widget"
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
        "Widget tells whether a number is positive.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: positivity.\n"
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
    write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT_TEXT)
    write(comp / "acceptance" / "AC-WIDGET-001.md", CRITERION_TEXT)
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nis_positive(n: int) -> bool\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    gen_dir = repo_root / "gen" / "widget"
    write(gen_dir / "widget.py", MODULE_SOURCE)

    assembler_source = (
        "CRITERION_TEXT = " + repr(CRITERION_TEXT) + "\n"
        "REQUIREMENT_TEXT = " + repr(REQUIREMENT_TEXT) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr("R-WIDGET-001") + ",\n"
        "        'criterion_text': CRITERION_TEXT,\n"
        "        'requirement_text': REQUIREMENT_TEXT,\n"
        "        'interface': " + repr("# Library\n\n```\nis_positive(n: int) -> bool\n```\n") + ",\n"
        "        'glossary': " + repr("# Glossary\n\n- **Widget** \u2014 a test term.\n") + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )

    conftest_source = (
        "import sys\n"
        "sys.path.insert(0, " + repr(str(gen_dir.resolve())) + ")\n"
        "import widget\n"
    )
    write(repo_root / "verification" / "widget" / "conftest.py", conftest_source)

    write(
        repo_root
        / "verification"
        / "widget"
        / "generated-test"
        / "test_ac_widget_001.py",
        header_line() + TEST_BODY,
    )


def test_mutation_score_is_one_with_conftest_pinning_original_module(tmp_path):
    repo_root = tmp_path.resolve() / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    log_path = tmp_path / "author_calls.log"

    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": header_line() + TEST_BODY,
            },
        }

    report = verifier_orchestrator.verify(
        "comp-widget", repo_root, test_author=test_author
    )

    criteria = field(report, "criteria")
    summary = [(field(c, "id"), field(c, "result")) for c in criteria]
    mutation_error = field(report, "mutation_error")
    mutation_score = field(report, "mutation_score")

    assert mutation_score == 1.0, (
        "mutation_score="
        + repr(mutation_score)
        + " mutation_error="
        + repr(mutation_error)
        + " criteria="
        + repr(summary)
    )