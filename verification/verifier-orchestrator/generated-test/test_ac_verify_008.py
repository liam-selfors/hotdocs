# hotdocs-criterion: sha256:1c21118bb3c268495525ef26f34826ec1209f8cc1881f1d236ef6b4c6e2de4c7
import json
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-fixwidget"
SLUG = "fixwidget"
MODULE = "fixwidget"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GENERATED_TEST_SOURCE = (
    "import " + MODULE + "\n"
    "\n"
    "\n"
    "def test_widget_value_is_one():\n"
    "    assert " + MODULE + ".widget_value() == 1\n"
)


def build_fixture(repo_root):
    repo_root = Path(repo_root)
    comp = repo_root / "specs" / "components" / SLUG

    write(
        repo_root / "specs" / "product" / "fixwidget.md",
        "---\n"
        "id: P-FIXWIDGET\n"
        "title: Fix widget capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Fix widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture capability.\n",
    )

    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Fix widget\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-FIXWIDGET]\n"
        "---\n"
        "\n"
        "# Fix widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Returns a fixed widget value.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widget_value.\n"
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
        "- Initial fixture.\n",
    )

    write(
        comp / "requirements" / "R-FIXWIDGET-001.md",
        "# R-FIXWIDGET-001\n\n"
        "**R-FIXWIDGET-001** - `widget_value()` MUST return 1.\n",
    )
    write(
        comp / "requirements" / "R-FIXWIDGET-002.md",
        "# R-FIXWIDGET-002\n\n"
        "**R-FIXWIDGET-002** - The spec MUST be clear.\n",
    )

    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nwidget_value() -> int\n```\n",
    )

    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        comp / "acceptance" / "AC-FIXWIDGET-001.md",
        "# AC-FIXWIDGET-001\n"
        "\n"
        "Covers: R-FIXWIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given the fixwidget module\n"
        "When widget_value is called\n"
        "Then it returns 1\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-FIXWIDGET-002.md",
        "# AC-FIXWIDGET-002\n"
        "\n"
        "Covers: R-FIXWIDGET-002\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the fixwidget spec\n"
        "When a reviewer reads it\n"
        "Then it is clear\n"
        "```\n",
    )

    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** - a thing.\n")

    # The component's own code: no mutation sites (numeric constants are never mutated).
    write(
        repo_root / "gen" / SLUG / (MODULE + ".py"),
        "def widget_value():\n    return 1\n",
    )

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    covers = {" + repr("AC-FIXWIDGET-001") + ": " + repr("R-FIXWIDGET-001") + ", "
        + repr("AC-FIXWIDGET-002") + ": " + repr("R-FIXWIDGET-002") + "}.get(criterion_id, '')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': covers,\n"
        "        'criterion_text': 'criterion text for ' + criterion_id,\n"
        "        'requirement_text': 'requirement text for ' + covers,\n"
        "        'interface': " + repr("# Library\n\n```\nwidget_value() -> int\n```") + ",\n"
        "        'glossary': " + repr("# Glossary") + ",\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n",
    )

    # test-probe stand-in: always ok, no findings.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport()\n",
    )


def make_judge(log_path):
    def judge(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("judge\n")
        return {"result": "pass", "rationale": "The spec is clear."}

    return judge


def make_test_author(log_path):
    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("test_author\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/fixwidget/generated-test/test_ac_fixwidget_001.py",
                "content": GENERATED_TEST_SOURCE,
            },
        }

    return test_author


def test_verify_twice_gives_identical_reports(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    judge_log = tmp_path / "judge.log"
    author_log = tmp_path / "author.log"
    judge = make_judge(judge_log)
    test_author = make_test_author(author_log)

    report1 = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, judge=judge, test_author=test_author
    )
    report2 = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, judge=judge, test_author=test_author
    )

    d1 = report1.to_dict()
    d2 = report2.to_dict()

    # The two reports are identical.
    assert d1 == d2
    assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)
    assert report1 == report2
    assert field(report1, "overall") == field(report2, "overall")
    assert field(report1, "criteria") == field(report2, "criteria")
    assert field(report1, "requirement_results") == field(report2, "requirement_results")

    # Sanity: the fixture really exercised both criteria in both runs.
    ids = sorted(field(c, "id") for c in field(report1, "criteria"))
    assert ids == ["AC-FIXWIDGET-001", "AC-FIXWIDGET-002"]
    results = {field(c, "id"): field(c, "result") for c in field(report1, "criteria")}
    assert results["AC-FIXWIDGET-001"] == "pass"
    assert results["AC-FIXWIDGET-002"] == "pass"
    assert d1["component_id"] == COMPONENT_ID

    judge_calls = judge_log.read_text(encoding="utf-8").splitlines() if judge_log.exists() else []
    assert len(judge_calls) >= 2
    assert len(judge_calls) % 2 == 0