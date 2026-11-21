# hotdocs-criterion: sha256:302eddf2a14a533f1df6773aef9c0d47c7b8b6af6f3840e665a543cd7bea0d38
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


CRITERION_ID = "AC-QUX-001"

BUNDLE_VALUES = {
    "component_id": "comp-qux",
    "criterion_id": CRITERION_ID,
    "covers": "R-QUX-001",
    "criterion_text": "Given a qux module\nWhen qux is called\nThen it returns 4",
    "requirement_text": "R-QUX-001: qux() MUST return twice baz().",
    "interface": "qux() -> int",
    "glossary": "Fixture glossary.",
    "dependency_interfaces": {},
    "testing": "",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def header_hex(bundle):
    keys = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    payload = json.dumps(
        {k: bundle[k] for k in keys},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def cached_test_source():
    return (
        "# hotdocs-criterion: sha256:" + header_hex(BUNDLE_VALUES) + "\n"
        "import qux\n"
        "\n"
        "\n"
        "def test_qux_returns_four():\n"
        "    assert qux.qux() == 4\n"
    )


def qux_source():
    return (
        "import importlib.util\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def _load_baz():\n"
        "    path = Path(__file__).resolve().parents[1] / \"baz\" / \"baz.py\"\n"
        "    spec = importlib.util.spec_from_file_location(\"baz\", path)\n"
        "    module = importlib.util.module_from_spec(spec)\n"
        "    spec.loader.exec_module(module)\n"
        "    return module\n"
        "\n"
        "\n"
        "def qux():\n"
        "    return 2 * _load_baz().baz()\n"
    )


def baz_source():
    return (
        "def baz():\n"
        "    return 2\n"
    )


def assembler_source(log_path):
    return (
        "BUNDLE = " + repr(BUNDLE_VALUES) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('assemble_criterion ' + str(criterion_id) + '\\n')\n"
        "    return dict(BUNDLE)\n"
    )


def probe_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
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
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return ProbeReport()\n"
    )


def build_fixture(repo_root, log_dir):
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Qux capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provides qux.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- qux only.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\nFixture glossary.\n")
    comp = repo_root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-QUX]\n"
        "---\n"
        "\n"
        "# Qux\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Returns twice baz.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- qux only.\n"
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
        "# R-QUX-001\n\n**R-QUX-001** — `qux()` MUST return twice `baz()`.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nqux() -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n"
        "\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a qux module\n"
        "When qux is called\n"
        "Then it returns 4\n"
        "```\n",
    )

    write(repo_root / "gen" / "qux" / "qux.py", qux_source())
    write(repo_root / "gen" / "baz" / "baz.py", baz_source())

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(log_dir / "assembler.log"),
    )
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        probe_source(log_dir / "probe.log"),
    )

    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        cached_test_source(),
    )


def make_test_author(log_path):
    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("test_author\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/qux/generated-test/test_ac_qux_001.py",
                "content": cached_test_source(),
            },
        }

    return author


def test_ac_verify_025_dependency_loaded_from_file_passes_with_full_score(tmp_path):
    repo_root = tmp_path / "repo"
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    repo_root.mkdir()
    build_fixture(repo_root, log_dir)

    report = verifier_orchestrator.verify(
        "comp-qux",
        repo_root,
        judge=None,
        test_author=make_test_author(log_dir / "author.log"),
    )

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1, criteria
    criterion = matching[0]
    assert field(criterion, "result") == "pass", criterion

    assert field(report, "mutation_error") is None, field(report, "mutation_error")
    assert field(report, "mutation_score") == 1.0, field(report, "mutation_score")