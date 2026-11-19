# hotdocs-criterion: sha256:2c81ac6e9f1f033f001b8ce842354325a36f5fc1226d9e9bfe4c516a5899e6fc
import hashlib
from pathlib import Path

import pytest

import verifier_orchestrator


CRITERION_TEXT = (
    "Given a calc module with g, h and m\n"
    "When g is invoked with 1 and 2\n"
    "Then it returns true"
)
REQUIREMENT_TEXT = "**R-CALC-001** — `g(a, b)` MUST return whether `a < b`."


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Calc** — a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "calc.md",
        "---\n"
        "id: P-CALC\n"
        "title: Calc capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Calc capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Compare and divide numbers.\n",
    )
    comp = repo_root / "specs" / "components" / "calc"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-calc\n"
        "title: Calc\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-CALC]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Calc\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Calc compares and divides numbers.\n",
    )
    write(comp / "requirements" / "R-CALC-001.md", "# R-CALC-001\n\n" + REQUIREMENT_TEXT + "\n")
    write(
        comp / "acceptance" / "AC-CALC-001.md",
        "# AC-CALC-001\n"
        "\n"
        "Covers: R-CALC-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        + CRITERION_TEXT
        + "\n```\n",
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

    # The component's real module: exactly three mutation sites.
    write(
        repo_root / "gen" / "calc" / "calc.py",
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
        "    return x\n",
    )

    # Stand-in spec-bundle-assembler.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "CRITERION_TEXT = " + repr(CRITERION_TEXT) + "\n"
        "REQUIREMENT_TEXT = " + repr(REQUIREMENT_TEXT) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-CALC-001',\n"
        "        'criterion_text': CRITERION_TEXT,\n"
        "        'requirement_text': REQUIREMENT_TEXT,\n"
        "        'interface': '# Library',\n"
        "        'glossary': '# Glossary',\n"
        "        'dependency_interfaces': {},\n"
        "    }\n",
    )

    # Cached generated-test with a correct header; kills only the "a < b" mutant.
    digest = hashlib.sha256(
        (CRITERION_TEXT + "\n" + REQUIREMENT_TEXT).encode("utf-8")
    ).hexdigest()
    write(
        repo_root / "verification" / "calc" / "generated-test" / "test_ac_calc_001.py",
        "# hotdocs-criterion: sha256:" + digest + "\n"
        "import calc\n"
        "\n"
        "\n"
        "def test_g_orders():\n"
        "    assert calc.g(1, 2) is True\n"
        "    assert calc.g(2, 1) is False\n",
    )


def test_mutation_score_is_one_third(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    report = verifier_orchestrator.verify("comp-calc", repo_root)

    criteria = field(report, "criteria")
    results = {field(c, "id"): field(c, "result") for c in criteria}
    assert results.get("AC-CALC-001") == "pass", criteria

    assert field(report, "mutation_error") is None
    score = field(report, "mutation_score")
    assert score is not None
    assert score == pytest.approx(1 / 3)