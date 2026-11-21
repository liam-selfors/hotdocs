# hotdocs-criterion: sha256:914ffd4f73bb8351da9062935e969f29f515dbc5eb7da17e3b45d033bfe0e476
# AC-VERIFY-010: a generated-test criterion with no cached test and no
# test_author configured is recorded as fail (failure_origin "test"),
# never skipped, and the overall verdict is fail.
from pathlib import Path

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


def build_fixture(repo_root, log_path):
    comp = repo_root / "specs" / "components" / SLUG

    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets get sized.\n",
    )
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a thing that has a size.\n",
    )
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Computes the size of a widget.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: sizing widgets.\n"
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
        "- Initial draft.\n",
    )
    write(
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "**" + REQUIREMENT_ID + "** — `widget_size(x)` MUST return `x`.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nwidget_size(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget of size 3\n"
        "When widget_size is called with it\n"
        "Then the returned size is 3\n"
        "```\n",
    )

    # The component's own code.
    write(repo_root / "gen" / SLUG / "widget.py", "def widget_size(x):\n    return x\n")

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('assemble_criterion ' + str(criterion_id) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(REQUIREMENT_ID) + ",\n"
        "        'criterion_text': 'Given a widget of size 3 When widget_size is called with it Then the returned size is 3',\n"
        "        'requirement_text': 'widget_size(x) MUST return x.',\n"
        "        'interface': 'widget_size(x: int) -> int',\n"
        "        'glossary': '',\n"
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
        "        self.tests_run = 0\n"
        "        self.tests_reached = 0\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport()\n",
    )


def test_generated_test_without_cache_or_author_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    build_fixture(repo_root, log_path)

    # No cached test exists anywhere under verification/.
    assert not (repo_root / "verification").exists()

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, judge=None, test_author=None)

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1, criteria
    entry = matching[0]

    assert field(entry, "result") != "skipped"
    assert field(entry, "result") == "fail"
    assert field(entry, "failure_origin") == "test"

    assert field(report, "overall") == "fail"