# hotdocs-criterion: sha256:d3888d93e18eb767b51760ac5a84aab1367f012b8e0b8713543b6b156c45de42
import shutil
from pathlib import Path

import verifier_orchestrator


SLUG = "widget"
COMPONENT_ID = "comp-widget"
CRITERION_ID = "AC-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def live_root():
    here = Path(verifier_orchestrator.__file__).resolve()
    gen_dir = next(p for p in here.parents if p.name == "gen")
    return (gen_dir / "spec-bundle-assembler").resolve().parents[1]


def assembler_source():
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr("R-WIDGET-001") + ",\n"
        "        'criterion_text': " + repr("Then foo equals 5") + ",\n"
        "        'requirement_text': " + repr("make_thing returns foo 5") + ",\n"
        "        'interface': " + repr("make_thing(x) -> Thing") + ",\n"
        "        'glossary': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n"
    )


def probe_source():
    return (
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 0\n"
        "        self.tests_reached = 0\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run,\n"
        "                'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "GATE_VERSION = 'test-probe@1.4.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    return _Report()\n"
    )


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Make widgets.\n",
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
        "Makes things.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: making things.\n"
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
        "# R-WIDGET-001\n"
        "\n"
        "**R-WIDGET-001** — `make_thing(x)` MUST return a `Thing` whose "
        "`foo` is 5.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "make_thing(x) -> Thing\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a seed is 1\n"
        "When make_thing is invoked with {\"x\": seed}\n"
        "Then foo equals 5\n"
        "```\n",
    )
    write(
        repo_root / "gen" / SLUG / (SLUG + ".py"),
        "import types\n"
        "\n"
        "\n"
        "def make_thing(x):\n"
        "    return types.SimpleNamespace(foo=3)\n",
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source())
    shutil.copytree(
        live_root() / "pipeline" / "criterion-compiler",
        repo_root / "pipeline" / "criterion-compiler",
        ignore=shutil.ignore_patterns("__pycache__"),
    )


def test_compiled_failure_detail_carries_expected_and_actual(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1, criteria
    criterion = matching[0]

    assert field(criterion, "result") == "fail", criterion
    detail = field(criterion, "failure_detail")
    assert detail is not None, criterion

    expected = field(detail, "expected")
    actual = field(detail, "actual")
    assert expected == 5, detail
    assert type(expected) is int, detail
    assert actual == 3, detail
    assert type(actual) is int, detail