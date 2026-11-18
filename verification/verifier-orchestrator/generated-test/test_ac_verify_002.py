# hotdocs-criterion: sha256:36189670b5334f5d814847c8b17867c5ad10e000b54a2743dba2316cdcf7dee5
import hashlib
from pathlib import Path

import verifier_orchestrator


CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"
COMPONENT_ID = "comp-widget"
SLUG = "widget"

CRITERION_TEXT = (
    "Given a number 2\n"
    "When double is called with it\n"
    "Then it returns 4"
)
REQUIREMENT_TEXT = "**R-WIDGET-001** — `double(x)` MUST return `2 * x`."


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, implementation_source):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "widgeting.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widgeting\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widgeting\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets double numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a number 2\n"
        "When it is doubled\n"
        "Then the result is 4\n"
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
        "# Library\n\n```\ndouble(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # Real code under gen/<slug>/
    write(repo_root / "gen" / SLUG / "widget.py", implementation_source)

    # spec-bundle-assembler stand-in
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
        "        'interface': " + repr("# Library\n\n```\ndouble(x: int) -> int\n```") + ",\n"
        "        'glossary': " + repr("# Glossary\n\n- **Widget** — a test term.") + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )

    # Already-generated (cached) test file with a correct header
    digest = hashlib.sha256(
        (CRITERION_TEXT + "\n" + REQUIREMENT_TEXT).encode("utf-8")
    ).hexdigest()
    cached_test = (
        "# hotdocs-criterion: sha256:" + digest + "\n"
        "import widget\n"
        "\n"
        "\n"
        "def test_double_two():\n"
        "    assert widget.double(2) == 4\n"
    )
    write(
        repo_root
        / "verification"
        / SLUG
        / "generated-test"
        / "test_ac_widget_001.py",
        cached_test,
    )


def make_test_author(log_path):
    def test_author_stub(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "stub-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": {"category": "stub", "message": "should not be called"},
            "file": None,
        }

    return test_author_stub


def find_criterion(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, criteria
    return matches[0]


def run_verify(tmp_path, implementation_source):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, implementation_source)
    log_path = tmp_path / "author_calls.log"
    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_test_author(log_path)
    )
    calls = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    return report, calls


def test_cached_generated_test_passes_against_correct_implementation(tmp_path):
    report, calls = run_verify(tmp_path, "def double(x):\n    return 2 * x\n")
    entry = find_criterion(report)
    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") == "pass"
    # The cached file was used, so no authoring dispatch happened.
    assert calls == ""


def test_cached_generated_test_fails_against_wrong_implementation(tmp_path):
    report, calls = run_verify(tmp_path, "def double(x):\n    return 2 * x + 1\n")
    entry = find_criterion(report)
    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") == "fail"
    assert calls == ""