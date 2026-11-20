# hotdocs-criterion: sha256:7a8fa0328db72411ea824cefbb7059c3eef08ec0782aab21f450cfc61d20552f
import hashlib
import json
import shutil
from pathlib import Path

import verifier_orchestrator


JS = "function f(a, b) { return a === b; }" + " " * 200

CRITERION_ID = "AC-QUX-001"

CRITERION_TEXT = (
    "# AC-QUX-001\n\n"
    "Covers: R-QUX-001\n"
    "Kind: generated-test\n\n"
    "```gherkin\n"
    "Given the qux module\n"
    "When qux is called\n"
    "Then it returns 4\n"
    "```\n"
)

REQUIREMENT_TEXT = "**R-QUX-001** - `qux()` MUST return 4.\n"

INTERFACE_TEXT = "# Library\n\n```\nqux() -> int\n```\n"

BUNDLE = {
    "component_id": "comp-qux",
    "criterion_id": CRITERION_ID,
    "covers": "R-QUX-001",
    "criterion_text": CRITERION_TEXT,
    "requirement_text": REQUIREMENT_TEXT,
    "interface": INTERFACE_TEXT,
    "glossary": "",
    "dependency_interfaces": {},
    "testing": "",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def header_line():
    payload = json.dumps(
        {k: BUNDLE[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cached_test_source():
    return (
        header_line() + "\n"
        + "import qux\n"
        + "\n\n"
        + "def test_qux_returns_four():\n"
        + "    assert qux.qux() == 4\n"
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def plant_compiler(root):
    live = (Path(verifier_orchestrator.__file__).resolve().parents[1] / "spec-bundle-assembler").resolve().parents[1]
    src = live / "pipeline" / "criterion-compiler"
    dst = root / "pipeline" / "criterion-compiler"
    if src.is_dir():
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
        return
    write(
        dst / "criterion_compiler.py",
        "GATE_VERSION = " + repr("criterion-compiler@1.0.0") + "\n"
        + "\n\n"
        + "class CompileReport:\n"
        + "    def __init__(self, outputs, gate_version, summary):\n"
        + "        self.outputs = outputs\n"
        + "        self.gate_version = gate_version\n"
        + "        self.summary = summary\n"
        + "\n\n"
        + "def compile(component_id, repo_root, target='pytest', out_dir=None):\n"
        + "    return CompileReport([], GATE_VERSION, {'compiled': 0, 'errors': 0, 'skipped_non_compiled_kind': 0})\n"
        + "\n\n"
        + "def compile_criterion(criterion, surface=None):\n"
        + "    return {'status': 'error', 'message': 'line 1: stand-in compiler'}\n",
    )


def build_fixture(root, qux_source):
    comp = root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-QUX]\n"
        "---\n\n"
        "# Qux\n\n"
        "## Purpose\n\nReturns four.\n\n"
        "## Scope\n\n- In scope: qux.\n\n"
        "## Definitions\n\nNone.\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n"
        "## Change log\n\n- Initial.\n",
    )
    write(comp / "requirements" / "R-QUX-001.md", REQUIREMENT_TEXT)
    write(comp / "acceptance" / (CRITERION_ID + ".md"), CRITERION_TEXT)
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n\n"
        "# Qux capability\n\n"
        "## Purpose\n\nQux.\n\n"
        "## Scope\n\n- Qux.\n",
    )
    write(root / "gen" / "qux" / "qux.py", qux_source)

    write(
        root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(BUNDLE) + "\n"
        + "\n\n"
        + "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        + "    return dict(BUNDLE)\n",
    )

    write(
        root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = " + repr("test-probe@1.3.0") + "\n"
        + "\n\n"
        + "class ProbeReport:\n"
        + "    def __init__(self):\n"
        + "        self.ok = True\n"
        + "        self.findings = []\n"
        + "        self.tests_run = 0\n"
        + "        self.tests_reached = 0\n"
        + "\n"
        + "    def to_dict(self):\n"
        + "        return {'ok': self.ok, 'findings': list(self.findings), 'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        + "\n\n"
        + "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        + "    return ProbeReport()\n",
    )

    plant_compiler(root)

    write(
        root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        cached_test_source(),
    )


def make_test_author(log_path):
    content = cached_test_source()

    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {"path": "verification/qux/generated-test/test_ac_qux_001.py", "content": content},
        }

    return test_author


def find_criterion(report, criterion_id):
    for c in field(report, "criteria"):
        if field(c, "id") == criterion_id:
            return c
    raise AssertionError("criterion " + criterion_id + " missing from report")


def test_javascript_in_string_fails_mutation(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    qux_source = '"""Doc."""\n\nSCRIPT = ' + repr(JS) + "\n\n\ndef qux():\n    return 4\n"
    build_fixture(root, qux_source)

    report = verifier_orchestrator.verify(
        "comp-qux", root, test_author=make_test_author(tmp_path / "author.log")
    )

    criterion = find_criterion(report, CRITERION_ID)
    assert field(criterion, "result") == "pass"
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"
    assert field(report, "mutation_error") == (
        "javascript in a string at qux.py:3; declare it as an asset "
        "(specs/architecture/asset-kinds.md)"
    )


def test_javascript_docstring_is_ignored(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    qux_source = repr(JS) + "\n\n\ndef qux():\n    return 4\n"
    build_fixture(root, qux_source)

    report = verifier_orchestrator.verify(
        "comp-qux", root, test_author=make_test_author(tmp_path / "author.log")
    )

    assert field(report, "mutation_error") is None
    assert field(report, "mutation_score") == 1.0