# hotdocs-criterion: sha256:ad5b4fbb76627c35da2b6b4b9da9d114ba51e0493e6a94e2031ec9c7588a68aa
# Test for AC-VERIFY-015 (covers R-VERIFY-006):
# Two generated-test criteria each fully test a different function of the
# same module. The mutation score is the union of both tests' kills (1.0),
# never either test's own score (0.4 or 0.6) nor their average (0.5).

from pathlib import Path

import pytest

import verifier_orchestrator


SLUG = "widgetmod"
COMPONENT_ID = "comp-" + SLUG

# alpha has 2 mutation sites (+ and *), beta has 3 (or, ==, <).
# Test 1 alone kills 2/5 = 0.4, test 2 alone kills 3/5 = 0.6, union = 1.0.
MODULE_SOURCE = (
    "def alpha(a, b):\n"
    "    return a + b * 2\n"
    "\n"
    "\n"
    "def beta(x, y):\n"
    "    return x == y or x < 0\n"
)

TEST_ALPHA_SOURCE = (
    "import widgetmod\n"
    "\n"
    "\n"
    "def test_alpha_values():\n"
    "    assert widgetmod.alpha(3, 4) == 11\n"
    "    assert widgetmod.alpha(0, 0) == 0\n"
)

TEST_BETA_SOURCE = (
    "import widgetmod\n"
    "\n"
    "\n"
    "def test_beta_values():\n"
    "    assert widgetmod.beta(2, 2) is True\n"
    "    assert widgetmod.beta(2, 3) is False\n"
    "    assert widgetmod.beta(-1, 5) is True\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, assembler_log, probe_log):
    comp_dir = repo_root / "specs" / "components" / SLUG

    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provides widget arithmetic.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widget arithmetic.\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given a widget system\n"
        "When it is used\n"
        "Then it computes\n"
        "```\n",
    )

    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** — a thing.\n")

    write(
        comp_dir / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget module\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget module\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Two small arithmetic helpers.\n"
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

    write(
        comp_dir / "requirements" / "R-WIDGETMOD-001.md",
        "# R-WIDGETMOD-001\n\n`alpha(a, b)` MUST return `a + b * 2`.\n",
    )
    write(
        comp_dir / "requirements" / "R-WIDGETMOD-002.md",
        "# R-WIDGETMOD-002\n\n`beta(x, y)` MUST return whether `x == y` or `x < 0`.\n",
    )

    write(
        comp_dir / "acceptance" / "AC-WIDGETMOD-001.md",
        "# AC-WIDGETMOD-001\n"
        "\n"
        "Covers: R-WIDGETMOD-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the widget module\n"
        "When alpha is called with 3 and 4\n"
        "Then it returns 11\n"
        "```\n",
    )
    write(
        comp_dir / "acceptance" / "AC-WIDGETMOD-002.md",
        "# AC-WIDGETMOD-002\n"
        "\n"
        "Covers: R-WIDGETMOD-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the widget module\n"
        "When beta is called with 2 and 2\n"
        "Then it returns true\n"
        "```\n",
    )

    write(
        comp_dir / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "alpha(a, b) -> int\n"
        "beta(x, y) -> bool\n"
        "```\n",
    )
    write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")

    # The module under test.
    write(repo_root / "gen" / SLUG / (SLUG + ".py"), MODULE_SOURCE)

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "COVERS = {\n"
        "    'AC-WIDGETMOD-001': 'R-WIDGETMOD-001',\n"
        "    'AC-WIDGETMOD-002': 'R-WIDGETMOD-002',\n"
        "}\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(" + repr(str(assembler_log)) + ", 'a') as fh:\n"
        "        fh.write(str(criterion_id) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': COVERS.get(criterion_id, ''),\n"
        "        'criterion_text': 'criterion ' + str(criterion_id),\n"
        "        'requirement_text': 'requirement for ' + str(criterion_id),\n"
        "        'interface': 'alpha(a, b) -> int\\nbeta(x, y) -> bool',\n"
        "        'glossary': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n",
    )

    # test-probe stand-in: always ok, no findings.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.3.0'\n"
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(" + repr(str(probe_log)) + ", 'a') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n",
    )


def make_test_author(log_path):
    sources = {
        "AC-WIDGETMOD-001": TEST_ALPHA_SOURCE,
        "AC-WIDGETMOD-002": TEST_BETA_SOURCE,
    }

    def test_author_stand_in(bundle):
        criterion_id = field(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(criterion_id) + "\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/" + SLUG + "/generated-test/test_"
                + criterion_id.lower().replace("-", "_") + ".py",
                "content": sources[criterion_id],
            },
        }

    return test_author_stand_in


def test_mutation_score_is_union_of_both_tests_kills(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    author_log = logs / "author.log"
    assembler_log = logs / "assembler.log"
    probe_log = logs / "probe.log"

    build_fixture(repo_root, assembler_log, probe_log)

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_test_author(author_log)
    )

    # Both generated tests were authored by the stand-in.
    authored = author_log.read_text(encoding="utf-8").split()
    assert sorted(set(authored)) == ["AC-WIDGETMOD-001", "AC-WIDGETMOD-002"]

    # Both criteria pass against the unmutated code.
    criteria = {field(c, "id"): c for c in field(report, "criteria")}
    assert field(criteria["AC-WIDGETMOD-001"], "result") == "pass"
    assert field(criteria["AC-WIDGETMOD-002"], "result") == "pass"

    assert field(report, "mutation_error") is None

    score = field(report, "mutation_score")
    assert score is not None
    # Each test alone would score 0.4 (alpha's tests) or 0.6 (beta's tests)
    # against the whole module; their average would be 0.5. The union of
    # kills covers all five mutants.
    assert score != pytest.approx(0.4)
    assert score != pytest.approx(0.6)
    assert score != pytest.approx(0.5)
    assert score == pytest.approx(1.0)