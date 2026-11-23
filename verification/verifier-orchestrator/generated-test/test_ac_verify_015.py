# hotdocs-criterion: sha256:0547da69b31f72cf17929e550509b9c8552a8177b8f0270535eb21168504c7c7
import json
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-mutfix"
SLUG = "mutfix"
MODULE = "mutfix"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def module_source():
    return (
        "def alpha(x):\n"
        "    return x + 1\n"
        "\n"
        "\n"
        "def beta(a, b):\n"
        "    return a > b\n"
    )


def alpha_test_source():
    return (
        "import " + MODULE + "\n"
        "\n"
        "\n"
        "def test_alpha_increments():\n"
        "    assert " + MODULE + ".alpha(2) == 3\n"
        "    assert " + MODULE + ".alpha(-5) == -4\n"
        "    assert " + MODULE + ".alpha(0) == 1\n"
    )


def beta_test_source():
    return (
        "import " + MODULE + "\n"
        "\n"
        "\n"
        "def test_beta_compares():\n"
        "    assert " + MODULE + ".beta(3, 1) is True\n"
        "    assert " + MODULE + ".beta(1, 3) is False\n"
        "    assert " + MODULE + ".beta(2, 2) is False\n"
    )


def probe_stand_in_source():
    return (
        "GATE_VERSION = " + repr("test-probe@1.4.0") + "\n"
        "\n"
        "\n"
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    return _Report()\n"
    )


def assembler_stand_in_source():
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    covers = criterion_id.replace('AC-', 'R-', 1)\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': covers,\n"
        "        'criterion_text': 'criterion ' + criterion_id,\n"
        "        'requirement_text': 'requirement ' + covers,\n"
        "        'interface': 'alpha(x: int) -> int\\nbeta(a: int, b: int) -> bool',\n"
        "        'glossary': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n"
    )


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        repo_root / "specs" / "product" / "mutfix.md",
        "---\n"
        "id: P-MUTFIX\n"
        "title: Mutfix capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Mutfix capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Fixture capability.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Mutfix\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-MUTFIX]\n"
        "---\n"
        "\n"
        "# Mutfix\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Two small functions.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: alpha and beta.\n"
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
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "alpha(x: int) -> int\n"
        "beta(a: int, b: int) -> bool\n"
        "```\n",
    )
    write(
        comp / "requirements" / "R-MUTFIX-001.md",
        "# R-MUTFIX-001\n\n`alpha(x)` MUST return `x + 1`.\n",
    )
    write(
        comp / "requirements" / "R-MUTFIX-002.md",
        "# R-MUTFIX-002\n\n`beta(a, b)` MUST return whether `a` is greater than `b`.\n",
    )
    write(
        comp / "acceptance" / "AC-MUTFIX-001.md",
        "# AC-MUTFIX-001\n"
        "\n"
        "Covers: R-MUTFIX-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given an integer 2\n"
        "When alpha is called with it\n"
        "Then the result is 3\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-MUTFIX-002.md",
        "# AC-MUTFIX-002\n"
        "\n"
        "Covers: R-MUTFIX-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the integers 3 and 1\n"
        "When beta is called with them\n"
        "Then the result is true\n"
        "```\n",
    )
    write(repo_root / "gen" / SLUG / (MODULE + ".py"), module_source())
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_stand_in_source())
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_stand_in_source(),
    )


def make_author(log_path):
    sources = {
        "AC-MUTFIX-001": alpha_test_source(),
        "AC-MUTFIX-002": beta_test_source(),
    }

    def author(bundle):
        criterion_id = field(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(criterion_id) + "\n")
        name = "test_" + criterion_id.lower().replace("-", "_") + ".py"
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/" + SLUG + "/generated-test/" + name,
                "content": sources[criterion_id],
            },
        }

    return author


def test_mutation_score_is_union_of_both_tests_kills(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_author(log_path)
    )

    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert sorted(calls) == ["AC-MUTFIX-001", "AC-MUTFIX-002"]

    criteria = {field(c, "id"): c for c in field(report, "criteria")}
    assert field(criteria["AC-MUTFIX-001"], "result") == "pass"
    assert field(criteria["AC-MUTFIX-002"], "result") == "pass"

    assert field(report, "mutation_error") is None
    score = field(report, "mutation_score")
    assert score is not None
    # Each test alone kills only its own function's single mutant (0.5 of the
    # module); the union of both kills every mutant.
    assert score > 0.5
    assert score >= 0.8
    assert abs(score - 1.0) < 1e-9

    as_dict = report.to_dict()
    assert abs(as_dict["mutation_score"] - 1.0) < 1e-9
    json.dumps(as_dict)