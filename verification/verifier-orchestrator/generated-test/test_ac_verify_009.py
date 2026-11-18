# hotdocs-criterion: sha256:684b2943bde80133cf7bc14906bf486090f8e30f885e8c030552da66b5e3f75e
import json
from pathlib import Path

import pytest

import verifier_orchestrator


COMPONENT_ID = "comp-bar"
CRITERION_ID = "AC-BAR-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def plain_bundle(bundle):
    if isinstance(bundle, dict):
        return dict(bundle)
    keys = [
        "component_id",
        "criterion_id",
        "covers",
        "criterion_text",
        "requirement_text",
        "interface",
        "glossary",
        "dependency_interfaces",
    ]
    out = {}
    for k in keys:
        try:
            out[k] = bundle[k]
        except Exception:
            out[k] = getattr(bundle, k)
    return out


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def expected_bundle_data():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": "R-BAR-001",
        "criterion_text": "UNIQUE-CRITERION-TEXT-7731 Given a number 2 When double_it is called Then it returns 4",
        "requirement_text": "UNIQUE-REQUIREMENT-TEXT-5519 double_it(x) MUST return 2 * x.",
        "interface": "UNIQUE-INTERFACE-TEXT-4402 double_it(x: int) -> int",
        "glossary": "UNIQUE-GLOSSARY-TEXT-9087",
        "dependency_interfaces": {"comp-zzz": "UNIQUE-DEP-INTERFACE-3318"},
    }


def build_fixture(repo_root, assembler_log):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Bar** — a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "P-BAR.md",
        "---\n"
        "id: P-BAR\n"
        "title: Bar capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Bar capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubling numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
        "\n"
        "### CS-BAR-001\n"
        "\n"
        "Covers: P-BAR\n"
        "\n"
        "```gherkin\n"
        "Given a number 2\n"
        "When it is doubled\n"
        "Then the result is 4\n"
        "```\n",
    )
    comp = repo_root / "specs" / "components" / "bar"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-bar\n"
        "title: Bar\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-BAR]\n"
        "---\n"
        "\n"
        "# Bar\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Bar doubles a number.\n"
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
        comp / "requirements" / "R-BAR-001.md",
        "# R-BAR-001\n\n**R-BAR-001** — `double_it(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "acceptance" / "AC-BAR-001.md",
        "# AC-BAR-001\n"
        "\n"
        "Covers: R-BAR-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a number 2\n"
        "When double_it is called with it\n"
        "Then it returns 4\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble_it(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "gen" / "bar" / "bar.py",
        "def double_it(x):\n    return 2 * x\n",
    )
    assembler_source = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(assembler_log)) + "\n"
        "BUNDLE = " + repr(expected_bundle_data()) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps([component_id, criterion_id, str(repo_root)]) + '\\n')\n"
        "    return json.loads(json.dumps(BUNDLE))\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )


def authored_test_code(marker, passing):
    return (
        "MARKER = " + repr(str(marker)) + "\n"
        "\n"
        "\n"
        "def test_authored_marker():\n"
        "    with open(MARKER, 'a', encoding='utf-8') as f:\n"
        "        f.write('ran\\n')\n"
        "    assert " + ("True" if passing else "False") + "\n"
    )


@pytest.mark.parametrize("passing,expected_result", [(True, "pass"), (False, "fail")])
def test_generated_test_dispatches_assembler_bundle_and_runs_returned_code(
    tmp_path, passing, expected_result
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    assembler_log = logs / "assembler.log"
    author_log = logs / "author.log"
    marker = logs / "marker.txt"
    build_fixture(repo_root, assembler_log)

    # No cached test exists for the criterion.
    assert not (
        repo_root / "verification" / "bar" / "generated-test" / "test_ac_bar_001.py"
    ).exists()

    received = []
    code = authored_test_code(marker, passing)

    def test_author(bundle):
        received.append(bundle)
        with open(author_log, "a", encoding="utf-8") as f:
            f.write(json.dumps(plain_bundle(bundle), sort_keys=True) + "\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "mock-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/bar/generated-test/test_ac_bar_001.py",
                "content": code,
            },
            "model_call_error": None,
        }

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=test_author
    )

    # The assembler stand-in was asked for exactly this criterion's bundle.
    assert assembler_log.is_file()
    calls = [json.loads(l) for l in assembler_log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert any(c[0] == COMPONENT_ID and c[1] == CRITERION_ID for c in calls)

    # test_author invoked exactly once, with exactly the assembler's bundle.
    assert len(received) == 1
    author_lines = [l for l in author_log.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(author_lines) == 1
    assert plain_bundle(received[0]) == expected_bundle_data()
    assert json.loads(author_lines[0]) == expected_bundle_data()

    # The returned test code was executed.
    assert marker.is_file()
    assert "ran" in marker.read_text(encoding="utf-8")

    # And its outcome produced the criterion's result.
    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1
    entry = matching[0]
    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") == expected_result