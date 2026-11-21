# hotdocs-criterion: sha256:7b839744972dd90eaaa75eec424fc2ebda160c2ce44705574350cf0c15275867
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


BUNDLE = {
    "component_id": "comp-qux",
    "criterion_id": "AC-QUX-001",
    "covers": "R-QUX-001",
    "criterion_text": "Given baz() returns 2 When qux() is called Then it returns 4",
    "requirement_text": "R-QUX-001: qux() MUST return twice baz().",
    "interface": "qux() -> int",
    "glossary": "",
    "dependency_interfaces": {},
    "testing": "",
}


def header_for(bundle):
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, log_path):
    comp = repo_root / "specs" / "components" / "qux"
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
        "Doubles baz.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: qux.\n",
    )
    write(
        comp / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
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
        "- In scope: qux().\n"
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
        "# R-QUX-001\n\n**R-QUX-001** - `qux()` MUST return twice `baz()`.\n",
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
        "Given baz returns 2\n"
        "When qux is called\n"
        "Then it returns 4\n"
        "```\n",
    )

    write(
        repo_root / "gen" / "baz" / "baz.py",
        "def baz():\n"
        "    return 2\n",
    )
    write(
        repo_root / "gen" / "qux" / "qux.py",
        "import importlib.util\n"
        "from pathlib import Path\n"
        "\n"
        "_path = Path(__file__).resolve().parents[1] / 'baz' / 'baz.py'\n"
        "_spec = importlib.util.spec_from_file_location('baz', _path)\n"
        "_baz = importlib.util.module_from_spec(_spec)\n"
        "_spec.loader.exec_module(_baz)\n"
        "\n"
        "\n"
        "def qux():\n"
        "    return 2 * _baz.baz()\n",
    )

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(BUNDLE) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )

    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "class _Report:\n"
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
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return _Report()\n",
    )

    test_body = (
        "import qux\n"
        "\n"
        "\n"
        "def test_qux_doubles_baz():\n"
        "    assert qux.qux() == 4\n"
    )
    content = header_for(BUNDLE) + "\n" + test_body
    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        content,
    )
    return content


def make_test_author(log_path, content):
    def test_author_stub(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/qux/generated-test/test_ac_qux_001.py",
                "content": content,
            },
        }

    return test_author_stub


def test_ac_verify_025_dependency_loaded_by_path_scores_full(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "author.log"
    content = build_fixture(repo_root, log_path)

    report = verifier_orchestrator.verify(
        "comp-qux", repo_root, test_author=make_test_author(log_path, content)
    )

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == "AC-QUX-001"]
    assert len(matching) == 1
    assert field(matching[0], "result") == "pass"
    assert field(report, "mutation_error") is None
    assert field(report, "mutation_score") == 1.0