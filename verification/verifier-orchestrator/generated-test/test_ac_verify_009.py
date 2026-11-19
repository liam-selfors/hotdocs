# hotdocs-criterion: sha256:684b2943bde80133cf7bc14906bf486090f8e30f885e8c030552da66b5e3f75e
import json
from pathlib import Path

import pytest

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def expected_bundle():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQUIREMENT_ID,
        "criterion_text": "SENTINEL-CRITERION-TEXT-7f3a: Given a widget input 2 When bar_double runs Then it yields 4",
        "requirement_text": "SENTINEL-REQUIREMENT-TEXT-91bc: bar_double(x) MUST return 2 * x.",
        "interface": "SENTINEL-INTERFACE-TEXT-44de",
        "glossary": "SENTINEL-GLOSSARY-TEXT-0a12",
        "dependency_interfaces": {"comp-sentinel": "SENTINEL-DEP-INTERFACE-5e6f"},
    }


def build_fixture(repo_root, assembler_log):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** \u2014 a test term.\n",
    )
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
        "- In scope: doubling.\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a value is 2\n"
        "When widget.bar_double is invoked with [2]\n"
        "Then result equals 4\n"
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
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** \u2014 `bar_double(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget input of 2\n"
        "When bar_double is called with it\n"
        "Then it returns 4\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nbar_double(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        repo_root / "gen" / SLUG / "widget.py",
        "def bar_double(x):\n    return 2 * x\n",
    )

    assembler_source = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(assembler_log)) + "\n"
        "BUNDLE = " + repr(expected_bundle()) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps([component_id, criterion_id, str(repo_root)]) + '\\n')\n"
        "    result = dict(BUNDLE)\n"
        "    result['dependency_interfaces'] = dict(BUNDLE['dependency_interfaces'])\n"
        "    return result\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )


def bundle_as_dict(bundle):
    keys = list(expected_bundle().keys())
    if isinstance(bundle, dict):
        return dict(bundle)
    out = {}
    for key in keys:
        try:
            out[key] = bundle[key]
        except Exception:
            out[key] = getattr(bundle, key)
    return out


@pytest.mark.parametrize("passing", [True, False])
def test_generated_test_dispatches_exact_bundle_and_runs_returned_code(tmp_path, passing):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    assembler_log = logs / "assembler.log"
    author_log = logs / "author.log"
    marker = logs / "generated_test_ran.txt"

    build_fixture(repo_root, assembler_log)

    cached = (
        repo_root / "verification" / SLUG / "generated-test" / "test_ac_widget_001.py"
    )
    assert not cached.exists()

    expected_value = "4" if passing else "5"
    test_content = (
        "import widget\n"
        "\n"
        "\n"
        "def test_widget_doubles():\n"
        "    with open(" + repr(str(marker)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(" + repr("ran\n") + ")\n"
        "    assert widget.bar_double(2) == " + expected_value + "\n"
    )

    def fake_test_author(bundle):
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(bundle_as_dict(bundle), sort_keys=True) + "\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "mock-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": test_content,
            },
        }

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=fake_test_author
    )

    # assemble_criterion was the bundle's producer, called for this criterion
    assert assembler_log.exists(), "assemble_criterion was never called"
    assembler_calls = [
        json.loads(line)
        for line in assembler_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matching = [
        c
        for c in assembler_calls
        if c[0] == COMPONENT_ID
        and c[1] == CRITERION_ID
        and Path(c[2]).resolve() == repo_root.resolve()
    ]
    assert matching, assembler_calls

    # test_author was invoked exactly once, with exactly that CriterionBundle
    assert author_log.exists(), "test_author was never called"
    author_calls = [
        json.loads(line)
        for line in author_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(author_calls) == 1, author_calls
    assert author_calls[0] == expected_bundle()

    # the returned test code was executed
    assert marker.exists(), "the returned test code was never executed"
    assert "ran" in marker.read_text(encoding="utf-8")

    # and its run produced the criterion's result
    criteria = field(report, "criteria")
    entries = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(entries) == 1, criteria
    entry = entries[0]
    assert field(entry, "result") == ("pass" if passing else "fail")