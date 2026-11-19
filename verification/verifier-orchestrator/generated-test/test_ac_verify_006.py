# hotdocs-criterion: sha256:ddc202677cb56de12d87b25f20ca875cbbef58b2312d2af9bc2eda06de42fbb6
import importlib.util
import sys
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CRITERION_TEXT = "\n".join([
    "# AC-WIDGET-001",
    "",
    "Covers: R-WIDGET-001",
    "Kind: generated-test",
    "",
    "```gherkin",
    "Given a widget module",
    "When double is called with 3",
    "Then it returns 6",
    "```",
    "",
])

REQUIREMENT_TEXT = "\n".join([
    "# R-WIDGET-001",
    "",
    "**R-WIDGET-001** \u2014 `double(x)` MUST return `x + x`, and `is_big(x)` MUST return whether `x > 10`.",
    "",
])

LIBRARY_TEXT = "\n".join([
    "# Library",
    "",
    "```",
    "double(x: int) -> int",
    "is_big(x: int) -> bool",
    "```",
    "",
])

GLOSSARY_TEXT = "# Glossary\n\n- **Widget** \u2014 a test term.\n"

# Code with mutation sites (a binary `+` and a single-operator comparison)
# that the weak test below never exercises, so no mutant is killed.
MODULE_SOURCE = "\n".join([
    "def double(x):",
    "    return x + x",
    "",
    "",
    "def is_big(x):",
    "    return x > 10",
    "",
])

# A test that passes on the unmutated module but kills no mutant.
WEAK_TEST_SOURCE = "\n".join([
    "import widget",
    "",
    "",
    "def test_widget_has_double():",
    "    assert hasattr(widget, " + repr("double") + ")",
    "",
])


def build_fixture(repo_root, log_path):
    specs = repo_root / "specs"
    write(specs / "glossary.md", GLOSSARY_TEXT)
    write(specs / "product" / "widget-cap.md", "\n".join([
        "---",
        "id: P-WIDGET",
        "title: Widget Capability",
        "status: draft",
        "owners: [team-a]",
        "---",
        "",
        "# Widget Capability",
        "",
        "## Purpose",
        "",
        "Widgets double numbers.",
        "",
        "## Scope",
        "",
        "- In scope: doubling.",
        "",
        "## Capability scenarios",
        "",
        "### CS-WIDGET-001",
        "",
        "Covers: P-WIDGET",
        "",
        "```gherkin",
        "Given a widget",
        "When it doubles 3",
        "Then it yields 6",
        "```",
        "",
    ]))
    comp = specs / "components" / "widget"
    write(comp / "component.md", "\n".join([
        "---",
        "id: comp-widget",
        "title: Widget",
        "status: draft",
        "owners: [team-a]",
        "realizes: [P-WIDGET]",
        "depends_on: []",
        "---",
        "",
        "# Widget",
        "",
        "## Purpose",
        "",
        "Widget doubles a number and tells whether a number is big.",
        "",
        "## Scope",
        "",
        "- In scope: doubling.",
        "",
        "## Definitions",
        "",
        "None.",
        "",
        "## Behavior",
        "",
        "See `requirements/`.",
        "",
        "## Interfaces",
        "",
        "See `interface/`.",
        "",
        "## Data",
        "",
        "See `interface/data/`.",
        "",
        "## Acceptance criteria",
        "",
        "See `acceptance/`.",
        "",
        "## Non-functional constraints",
        "",
        "See `constraints.md`.",
        "",
        "## Open questions",
        "",
        "## Change log",
        "",
        "- Initial.",
        "",
    ]))
    write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT_TEXT)
    write(comp / "acceptance" / "AC-WIDGET-001.md", CRITERION_TEXT)
    write(comp / "interface" / "library.md", LIBRARY_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(repo_root / "gen" / "widget" / "widget.py", MODULE_SOURCE)

    assembler_source = "\n".join([
        "def assemble_criterion(component_id, criterion_id, repo_root):",
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:",
        "        fh.write('assemble_criterion ' + str(criterion_id) + '\\n')",
        "    return {",
        "        'component_id': component_id,",
        "        'criterion_id': criterion_id,",
        "        'covers': 'R-WIDGET-001',",
        "        'criterion_text': " + repr(CRITERION_TEXT) + ",",
        "        'requirement_text': " + repr(REQUIREMENT_TEXT) + ",",
        "        'interface': " + repr(LIBRARY_TEXT) + ",",
        "        'glossary': " + repr(GLOSSARY_TEXT) + ",",
        "        'dependency_interfaces': {},",
        "    }",
        "",
    ])
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )


def make_test_author(log_path):
    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("test_author\n")
        return {
            "component_id": "comp-widget",
            "criterion_id": "AC-WIDGET-001",
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": WEAK_TEST_SOURCE,
            },
        }

    return test_author


def test_mutation_score_below_bar_fails_overall(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    log_path.write_text("", encoding="utf-8")
    build_fixture(repo_root, log_path)

    report = verifier_orchestrator.verify(
        "comp-widget", repo_root, test_author=make_test_author(log_path)
    )

    log = log_path.read_text(encoding="utf-8")
    assert "test_author" in log

    criteria = field(report, "criteria")
    by_id = {field(c, "id"): c for c in criteria}
    assert "AC-WIDGET-001" in by_id
    crit = by_id["AC-WIDGET-001"]
    assert field(crit, "kind") == "generated-test"
    # The weak test passes on the unmutated code; mutation score never
    # changes a criterion's own result.
    assert field(crit, "result") == "pass"

    # The baseline passed, so a real score was computed and no error set.
    assert field(report, "mutation_error") is None
    score = field(report, "mutation_score")
    assert score is not None
    assert score < 0.8

    # The overall verdict fails, citing the mutation-score shortfall.
    assert field(report, "overall") == "fail"

    as_dict = report.to_dict()
    assert as_dict["overall"] == "fail"
    assert as_dict["mutation_score"] is not None
    assert as_dict["mutation_score"] < 0.8
    assert as_dict["mutation_error"] is None