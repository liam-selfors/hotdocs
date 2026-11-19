# hotdocs-criterion: sha256:becdc06e54ef2c48ef7acfba5628529da2f06cf54f2703b959a4967163309079
import hashlib
from pathlib import Path

import pytest

import verifier_orchestrator


NOTE = "a === b && c"
SCRIPT = "function f(a, b) { var s = 'it\\'s === no'; /* a && b */ return a === b; // c || d\n}"
PAGE = "<p>a === b</p><script>let t = x + 1 - -y;</script>"

CRITERION_TEXT = "Given the qux module\nWhen script is called\nThen it returns the script text"
REQUIREMENT_TEXT = "**R-QUX-001** — `script()` MUST return the script text."


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def qux_source():
    return (
        "NOTE = " + repr(NOTE) + "\n\n\n"
        + "def script():\n    return " + repr(SCRIPT) + "\n\n\n"
        + "def page():\n    return " + repr(PAGE) + "\n"
    )


def assembler_source():
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-QUX-001',\n"
        "        'criterion_text': " + repr(CRITERION_TEXT) + ",\n"
        "        'requirement_text': " + repr(REQUIREMENT_TEXT) + ",\n"
        "        'interface': " + repr("# Library\n\n```\nscript() -> str\npage() -> str\n```") + ",\n"
        "        'glossary': " + repr("# Glossary\n\n- **Qux** — a test term.") + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )


def header_line():
    digest = hashlib.sha256(
        (CRITERION_TEXT + "\n" + REQUIREMENT_TEXT).encode("utf-8")
    ).hexdigest()
    return "# hotdocs-criterion: sha256:" + digest + "\n"


def build_fixture(repo_root, test_body):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Qux** — a test term.\n")
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Qux capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Qux returns fixed strings.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: qux.\n",
    )
    comp = repo_root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-QUX]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Qux\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Qux returns fixed strings.\n",
    )
    write(comp / "requirements" / "R-QUX-001.md", "# R-QUX-001\n\n" + REQUIREMENT_TEXT + "\n")
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n"
        "\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        + CRITERION_TEXT + "\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nscript() -> str\npage() -> str\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(repo_root / "gen" / "qux" / "qux.py", qux_source())
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        header_line() + test_body,
    )


def criterion(report, criterion_id):
    for c in field(report, "criteria"):
        if field(c, "id") == criterion_id:
            return c
    raise AssertionError("criterion " + criterion_id + " missing from report")


def test_script_equality_kills_one_of_three_mutants(tmp_path):
    repo_root = tmp_path / "repo"
    body = (
        "import qux\n"
        "\n"
        "\n"
        "def test_script():\n"
        "    assert qux.script() == " + repr(SCRIPT) + "\n"
    )
    build_fixture(repo_root, body)

    report = verifier_orchestrator.verify("comp-qux", repo_root)

    assert field(criterion(report, "AC-QUX-001"), "result") == "pass"
    assert field(report, "mutation_error") is None
    score = field(report, "mutation_score")
    assert score is not None
    assert score == pytest.approx(1 / 3, abs=1e-9)


def test_weak_test_kills_nothing_and_fails_overall(tmp_path):
    repo_root = tmp_path / "repo"
    body = (
        "import qux\n"
        "\n"
        "\n"
        "def test_script():\n"
        "    assert " + repr("function") + " in qux.script()\n"
    )
    build_fixture(repo_root, body)

    report = verifier_orchestrator.verify("comp-qux", repo_root)

    assert field(criterion(report, "AC-QUX-001"), "result") == "pass"
    score = field(report, "mutation_score")
    assert score is not None
    assert score == 0.0
    assert field(report, "overall") == "fail"