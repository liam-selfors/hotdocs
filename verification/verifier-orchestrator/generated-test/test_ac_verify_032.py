# hotdocs-criterion: sha256:4062132fd7af7964d9c7462a901db5df195888a52d3d526cfd1be9953b4ab449
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


JS = "function f(a, b) { return a === b; }" + " " * 200

CRITERION_ID = "AC-QUX-001"
COMPONENT_ID = "comp-qux"

BUNDLE = {
    "component_id": COMPONENT_ID,
    "criterion_id": CRITERION_ID,
    "covers": "R-QUX-001",
    "criterion_text": "Given the qux module\nWhen qux.qux is invoked\nThen it returns 4",
    "requirement_text": "R-QUX-001: qux() MUST return 4.",
    "interface": "# Library\n\n```\nqux() -> int\n```\n",
    "glossary": "# Glossary\n",
    "dependency_interfaces": {},
    "testing": "",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def header_for(bundle):
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cached_test_source():
    return (
        header_for(BUNDLE) + "\n"
        + "import qux\n"
        + "\n"
        + "\n"
        + "def test_qux_returns_four():\n"
        + "    assert qux.qux() == 4\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, qux_source):
    comp = repo_root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\n"
        + "id: comp-qux\n"
        + "title: Qux\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "depends_on: []\n"
        + "realizes: [P-QUX]\n"
        + "---\n"
        + "\n"
        + "# Qux\n\n"
        + "## Purpose\n\nReturns four.\n\n"
        + "## Scope\n\n- In scope: qux.\n\n"
        + "## Definitions\n\nNone.\n\n"
        + "## Behavior\n\nSee `requirements/`.\n\n"
        + "## Interfaces\n\nSee `interface/`.\n\n"
        + "## Data\n\nSee `interface/data/`.\n\n"
        + "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        + "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        + "## Open questions\n\n"
        + "## Change log\n\n- Initial.\n",
    )
    write(comp / "requirements" / "R-QUX-001.md", "**R-QUX-001** — `qux()` MUST return 4.\n")
    write(comp / "interface" / "library.md", "# Library\n\n```\nqux() -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n\n"
        + "Covers: R-QUX-001\n"
        + "Kind: generated-test\n\n"
        + "```gherkin\n"
        + "Given the qux module\n"
        + "When qux.qux is invoked\n"
        + "Then it returns 4\n"
        + "```\n",
    )
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        + "id: P-QUX\n"
        + "title: Qux capability\n"
        + "status: draft\n"
        + "owners: [pipeline-team]\n"
        + "---\n\n"
        + "# Qux capability\n\n## Purpose\n\nFour.\n\n## Scope\n\n- Four.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    # Code under test.
    write(repo_root / "gen" / "qux" / "qux.py", qux_source)

    # Stand-in spec-bundle-assembler.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(BUNDLE) + "\n"
        + "\n"
        + "\n"
        + "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        + "    return dict(BUNDLE)\n",
    )

    # Stand-in test-probe: always ok.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "class ProbeReport:\n"
        + "    def __init__(self):\n"
        + "        self.ok = True\n"
        + "        self.findings = []\n"
        + "        self.tests_run = 1\n"
        + "        self.tests_reached = 1\n"
        + "\n"
        + "    def to_dict(self):\n"
        + "        return {'ok': self.ok, 'findings': list(self.findings), 'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        + "\n"
        + "\n"
        + "GATE_VERSION = 'test-probe@1.3.0'\n"
        + "\n"
        + "\n"
        + "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        + "    return ProbeReport()\n",
    )

    # The one cached, current generated test.
    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        cached_test_source(),
    )


def make_test_author(log_path):
    def test_author(bundle):
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
                "content": cached_test_source(),
            },
        }

    return test_author


def criterion_entry(report, criterion_id):
    for c in field(report, "criteria"):
        if field(c, "id") == criterion_id:
            return c
    raise AssertionError("criterion " + criterion_id + " missing from report")


def test_javascript_in_string_constant_fails_mutation(tmp_path):
    repo_root = tmp_path / "repo"
    qux_source = (
        '"""Doc."""\n\nSCRIPT = ' + repr(JS) + "\n\n\ndef qux():\n    return 4\n"
    )
    build_fixture(repo_root, qux_source)
    assert (repo_root / "gen" / "qux" / "qux.py").read_text(encoding="utf-8").splitlines()[2].startswith("SCRIPT = ")

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_test_author(tmp_path / "author.log")
    )

    entry = criterion_entry(report, CRITERION_ID)
    assert field(entry, "result") == "pass"
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"
    assert field(report, "mutation_error") == (
        "javascript in a string at qux.py:3; declare it as an asset "
        "(specs/architecture/asset-kinds.md)"
    )


def test_javascript_docstring_is_ignored(tmp_path):
    repo_root = tmp_path / "repo"
    qux_source = repr(JS) + "\n\n\ndef qux():\n    return 4\n"
    build_fixture(repo_root, qux_source)

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_test_author(tmp_path / "author.log")
    )

    entry = criterion_entry(report, CRITERION_ID)
    assert field(entry, "result") == "pass"
    assert field(report, "mutation_error") is None
    assert field(report, "mutation_score") == 1.0