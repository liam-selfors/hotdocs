# hotdocs-criterion: sha256:00ff5e4d560b94a96caeabf9c1fcaa7fbcedaa2216b8e51bdebdd4a501d8f7d9
import hashlib
from pathlib import Path

import verifier_orchestrator


CRITERION_ID = "AC-QUX-001"
COVERS = "R-QUX-001"

CRITERION_TEXT = (
    "Given a qux component is ready\n"
    "When qux is called\n"
    "Then it returns 4"
)
REQUIREMENT_TEXT = "**R-QUX-001** — `qux()` MUST return `4`."


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def header_line():
    digest = hashlib.sha256(
        (CRITERION_TEXT + "\n" + REQUIREMENT_TEXT).encode("utf-8")
    ).hexdigest()
    return "# hotdocs-criterion: sha256:" + digest


def assembler_source():
    return (
        "CRITERION_TEXT = " + repr(CRITERION_TEXT) + "\n"
        "REQUIREMENT_TEXT = " + repr(REQUIREMENT_TEXT) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(COVERS) + ",\n"
        "        'criterion_text': CRITERION_TEXT,\n"
        "        'requirement_text': REQUIREMENT_TEXT,\n"
        "        'interface': " + repr("# Library\n\n```\nqux() -> int\n```") + ",\n"
        "        'glossary': " + repr("# Glossary\n\n- **Qux** — a test term.") + ",\n"
        "        'dependency_interfaces': {},\n"
        "        'module_names': ['qux'],\n"
        "    }\n"
    )


def build_fixture(repo_root, qux_source, extra_gen, cached_test_body):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Qux** — a test term.\n",
    )
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
        "Qux returns four.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: qux.\n"
        "\n"
        "### CS-QUX-001\n"
        "\n"
        "Covers: P-QUX\n"
        "\n"
        "```gherkin\n"
        "Given a qux system is ready\n"
        "When qux is called\n"
        "Then it returns 4\n"
        "```\n",
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
        "Qux returns four.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: qux.\n"
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
        comp / "requirements" / "R-QUX-001.md",
        "# R-QUX-001\n\n" + REQUIREMENT_TEXT + "\n",
    )
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n"
        "\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n" + CRITERION_TEXT + "\n```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nqux() -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    write(repo_root / "gen" / "qux" / "qux.py", qux_source)
    for rel, text in extra_gen.items():
        write(repo_root / "gen" / rel, text)

    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        header_line() + "\n" + cached_test_body,
    )


def find_criterion(report, criterion_id):
    for c in field(report, "criteria"):
        if field(c, "id") == criterion_id:
            return c
    raise AssertionError("criterion not in report: " + repr(criterion_id))


def test_mutation_sandbox_reaches_dependency_by_path(tmp_path):
    repo_root = tmp_path / "repo"
    qux_source = (
        "import importlib.util\n"
        "from pathlib import Path\n"
        "\n"
        "_BAZ_PATH = Path(__file__).resolve().parents[1] / \"baz\" / \"baz.py\"\n"
        "_spec = importlib.util.spec_from_file_location(\"baz\", _BAZ_PATH)\n"
        "_baz = importlib.util.module_from_spec(_spec)\n"
        "_spec.loader.exec_module(_baz)\n"
        "baz = _baz.baz\n"
        "\n"
        "\n"
        "def qux():\n"
        "    return 2 * baz()\n"
    )
    baz_source = "def baz():\n    return 2\n"
    cached_test_body = (
        "import qux\n"
        "\n"
        "\n"
        "def test_qux():\n"
        "    assert qux.qux() == 4\n"
    )
    build_fixture(
        repo_root,
        qux_source,
        {"baz/baz.py": baz_source},
        cached_test_body,
    )

    report = verifier_orchestrator.verify("comp-qux", repo_root)

    criterion = find_criterion(report, CRITERION_ID)
    assert field(criterion, "result") == "pass"
    assert field(report, "mutation_error") is None
    assert field(report, "mutation_score") == 1.0


def test_mutation_baseline_fails_in_sandbox(tmp_path):
    repo_root = tmp_path / "repo"
    qux_source = "def qux():\n    return 2 * 2\n"
    cached_test_body = (
        "from pathlib import Path\n"
        "\n"
        "import qux\n"
        "\n"
        "\n"
        "def test_qux():\n"
        "    assert qux.qux() == 4\n"
        "    assert (Path.cwd() / \"specs\").is_dir()\n"
    )
    build_fixture(repo_root, qux_source, {}, cached_test_body)

    report = verifier_orchestrator.verify("comp-qux", repo_root)

    criterion = find_criterion(report, CRITERION_ID)
    assert field(criterion, "result") == "pass"
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"
    assert (
        field(report, "mutation_error")
        == "mutation baseline failed in the sandbox: pytest exited 1"
    )