# hotdocs-criterion: sha256:d785875974b7c18c5d6a5fe9dc43481eb3ab577cef0443be6a77afb91470f150
import verifier_orchestrator

import shutil
from pathlib import Path


SLUG = "acme-widget"
MODULE = "acme_widget"
COMPONENT_ID = "comp-acme-widget"
CRITERION_ID = "AC-ACME-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def live_root():
    return (
        Path(verifier_orchestrator.__file__).resolve().parents[1]
        / "spec-bundle-assembler"
    ).resolve().parents[1]


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / SLUG

    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a thing with a foo.\n",
    )

    write(
        repo_root / "specs" / "product" / "acme.md",
        "---\n"
        "id: P-ACME\n"
        "title: Acme capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Acme capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Make widgets.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widgets.\n"
        "\n"
        "### CS-ACME-001\n"
        "\n"
        "Covers: P-ACME\n"
        "\n"
        "```gherkin\n"
        "Given a seed is 1\n"
        "When make_widget is invoked with {\"x\": seed}\n"
        "Then foo equals 5\n"
        "```\n",
    )

    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Acme Widget\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-ACME]\n"
        "---\n"
        "\n"
        "# Acme Widget\n"
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
        comp / "requirements" / "R-ACME-001.md",
        "**R-ACME-001** — `make_widget(x)` MUST return a widget whose "
        "`foo` is 5.\n",
    )

    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "make_widget(x: int) -> Widget\n"
        "```\n",
    )

    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: R-ACME-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a seed is 1\n"
        "When make_widget is invoked with {\"x\": seed}\n"
        "Then foo equals 5\n"
        "```\n",
    )

    # Generated code under test: result.foo is 3, not 5.
    write(
        repo_root / "gen" / SLUG / (MODULE + ".py"),
        "class Widget:\n"
        "    def __init__(self, foo):\n"
        "        self.foo = foo\n"
        "\n"
        "\n"
        "def make_widget(x):\n"
        "    return Widget(3)\n",
    )

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-ACME-001',\n"
        "        'criterion_text': 'criterion text',\n"
        "        'requirement_text': 'requirement text',\n"
        "        'interface': 'make_widget(x: int) -> Widget',\n"
        "        'glossary': 'glossary',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n",
    )

    # test-probe stand-in: always ok.
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
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport()\n",
    )

    # The real criterion-compiler, copied into repo_root.
    src = live_root() / "pipeline" / "criterion-compiler"
    dst = repo_root / "pipeline" / "criterion-compiler"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))


def test_ac_verify_013(tmp_path):
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