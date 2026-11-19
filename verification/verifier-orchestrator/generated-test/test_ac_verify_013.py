# hotdocs-criterion: sha256:11172d0fbb864ab78678f1166b06e1a64795be2e5fc5d996643385ac74875160
import shutil
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CRITERION_TEXT = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given a seed is 1\n"
    "When compute is invoked with {\"x\": seed}\n"
    "Then foo equals 5\n"
    "```\n"
)

REQUIREMENT_TEXT = (
    "# R-WIDGET-001\n"
    "\n"
    "**R-WIDGET-001** \u2014 `compute(x)` MUST return a value whose `foo` is `5`.\n"
)

INTERFACE_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "compute(x: int) -> object\n"
    "```\n"
)


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** \u2014 a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "widget-cap.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets compute things.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widgets.\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "\n"
        "```gherkin\n"
        "Given a seed is 1\n"
        "When compute is invoked with {\"x\": seed}\n"
        "Then foo equals 5\n"
        "```\n",
    )
    comp = repo_root / "specs" / "components" / "widget"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-WIDGET]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget computes a value.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: computing.\n"
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
    write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT_TEXT)
    write(comp / "acceptance" / "AC-WIDGET-001.md", CRITERION_TEXT)
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # Generated code under test: returns foo == 3, not the expected 5.
    write(
        repo_root / "gen" / "widget" / "widget.py",
        "import types\n"
        "\n"
        "\n"
        "def compute(x):\n"
        "    return types.SimpleNamespace(foo=3)\n",
    )

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-WIDGET-001',\n"
        "        'criterion_text': " + repr(CRITERION_TEXT) + ",\n"
        "        'requirement_text': " + repr(REQUIREMENT_TEXT) + ",\n"
        "        'interface': " + repr(INTERFACE_TEXT) + ",\n"
        "        'glossary': '# Glossary',\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'spec_bundle_hash': 'sha256:' + '0' * 64,\n"
        "        'spec': '',\n"
        "        'interface': " + repr(INTERFACE_TEXT) + ",\n"
        "        'constraints': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'dependency_context': {},\n"
        "        'dependency_usage': {},\n"
        "        'vars': {},\n"
        "        'glossary': '# Glossary',\n"
        "        'hint_code': None,\n"
        "    }\n",
    )

    # Real criterion-compiler, copied from the live tree.
    live = (
        Path(verifier_orchestrator.__file__).resolve().parents[1]
        / "spec-bundle-assembler"
    ).resolve().parents[1]
    src = live / "pipeline" / "criterion-compiler"
    dst = repo_root / "pipeline" / "criterion-compiler"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))


def test_ac_verify_013_failure_detail_expected_and_actual(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    report = verifier_orchestrator.verify("comp-widget", repo_root)

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == "AC-WIDGET-001"]
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