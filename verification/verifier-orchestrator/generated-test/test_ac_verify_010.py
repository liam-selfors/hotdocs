# hotdocs-criterion: sha256:a55057536f7020749ed0cc7513c04b34e0353439759ba494fa1f9c43ab3e6a4c
import json
from pathlib import Path

import verifier_orchestrator


SLUG = "widget"
COMPONENT_ID = "comp-widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def assembler_source():
    bundle = {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQUIREMENT_ID,
        "criterion_text": "Given a widget\nWhen it is built\nThen it works",
        "requirement_text": "The widget MUST work.",
        "interface": "# Library\n\n```\nbuild_widget(n: int) -> int\n```\n",
        "glossary": "# Glossary\n",
        "dependency_interfaces": {},
        "testing": "",
    }
    return (
        "import copy\n"
        "\n"
        "_BUNDLE = " + repr(bundle) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    bundle = copy.deepcopy(_BUNDLE)\n"
        "    bundle['component_id'] = component_id\n"
        "    bundle['criterion_id'] = criterion_id\n"
        "    return bundle\n"
    )


def probe_source():
    return (
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 0\n"
        "        self.tests_reached = 0\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport()\n"
    )


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "product" / "widget-cap.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Builds widgets.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widgets.\n"
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
        "# " + REQUIREMENT_ID + "\n\n**" + REQUIREMENT_ID + "** \u2014 The widget MUST work.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nbuild_widget(n: int) -> int\n```\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it is built\n"
        "Then it works\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "gen" / SLUG / (SLUG + ".py"), "")
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source())
    cached = repo_root / "verification" / SLUG / "generated-test" / "test_ac_widget_001.py"
    assert not cached.exists()


def find_criterion(criteria, criterion_id):
    for c in criteria:
        if field(c, "id") == criterion_id:
            return c
    raise AssertionError("criterion " + criterion_id + " missing from report")


def test_generated_test_without_cache_or_author_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, judge=None, test_author=None)

    criteria = field(report, "criteria")
    entry = find_criterion(criteria, CRITERION_ID)
    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") != "skipped"
    assert field(entry, "result") == "fail"
    assert field(entry, "failure_origin") == "test"
    assert field(report, "overall") == "fail"

    as_dict = report.to_dict()
    dict_entry = find_criterion(as_dict["criteria"], CRITERION_ID)
    assert dict_entry["result"] == "fail"
    assert dict_entry["failure_origin"] == "test"
    assert as_dict["overall"] == "fail"


def test_cli_reports_fail_for_unauthored_generated_test(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    code = verifier_orchestrator.main(
        [COMPONENT_ID, "--repo-root", str(repo_root), "--format=json"]
    )
    out = capsys.readouterr().out

    assert code == 1
    doc = json.loads(out)
    entry = find_criterion(doc["criteria"], CRITERION_ID)
    assert entry["result"] == "fail"
    assert entry["failure_origin"] == "test"
    assert doc["overall"] == "fail"