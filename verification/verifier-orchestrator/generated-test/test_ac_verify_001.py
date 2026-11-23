# hotdocs-criterion: sha256:24bea3122e9b18b3f262c71920216247086e6deaed75d0240fe54b0fbbc314b7
import importlib.util
import sys
from pathlib import Path

import pytest

import verifier_orchestrator


SLUG = "widgetry"
COMPONENT_ID = "comp-widgetry"
CRITERION_ID = "AC-WIDG-001"
REQUIREMENT_ID = "R-WIDG-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def emitted_source(expected):
    return (
        "import widgetry\n"
        "\n"
        "\n"
        "def test_ac_widg_001():\n"
        "    result = widgetry.bar_double(2)\n"
        "    assert result == " + repr(expected) + "\n"
    )


COMPILER_BODY = '''
import dataclasses
from pathlib import Path

GATE_VERSION = "criterion-compiler@1.0.0"


@dataclasses.dataclass
class ParsedCriterion:
    criterion_id: str = ""
    covers: str = ""
    kind: str = ""
    gherkin: str = ""
    file: str = ""


@dataclasses.dataclass
class InterfaceSurface:
    functions: dict = dataclasses.field(default_factory=dict)
    types: dict = dataclasses.field(default_factory=dict)
    module_name: str = ""


@dataclasses.dataclass
class CompileReport:
    outputs: list
    gate_version: str
    summary: dict


def _log(line):
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\\n")


def _cid(criterion):
    if isinstance(criterion, dict):
        return criterion.get("criterion_id")
    return getattr(criterion, "criterion_id", None)


def compile_criterion(criterion, surface=None):
    _log("compile_criterion " + str(_cid(criterion)))
    return {"status": "compiled", "source": SOURCE}


def compile(component_id, repo_root, target="pytest", out_dir=None):
    repo_root = Path(repo_root)
    slug = component_id[5:] if component_id.startswith("comp-") else component_id
    if out_dir is None:
        out = repo_root / "verification" / slug / "compiled"
    else:
        out = Path(out_dir)
        if not out.is_absolute():
            out = repo_root / out
    out.mkdir(parents=True, exist_ok=True)
    target_file = out / "test_ac_widg_001.py"
    target_file.write_text(SOURCE, encoding="utf-8")
    _log("compile " + str(component_id) + " AC-WIDG-001")
    try:
        rel = target_file.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        rel = str(target_file.resolve())
    return CompileReport(
        outputs=[{
            "criterion_id": "AC-WIDG-001",
            "covers": "R-WIDG-001",
            "status": "compiled",
            "file": rel,
        }],
        gate_version=GATE_VERSION,
        summary={"compiled": 1, "errors": 0, "skipped_non_compiled_kind": 0},
    )
'''


PROBE_SOURCE = '''
GATE_VERSION = "test-probe@1.4.0"


class _Report:
    def __init__(self):
        self.ok = True
        self.findings = []
        self.tests_run = 1
        self.tests_reached = 1

    def to_dict(self):
        return {"ok": True, "findings": [], "tests_run": 1, "tests_reached": 1}


def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,
          interpreter=None, assets=None):
    return _Report()
'''


ASSEMBLER_BODY = '''

def assemble_criterion(component_id, criterion_id, repo_root):
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": "R-WIDG-001",
        "criterion_text": CRITERION_TEXT,
        "requirement_text": "R-WIDG-001 text",
        "interface": "bar_double(x: int) -> int",
        "glossary": "",
        "dependency_interfaces": {},
        "testing": "",
    }
'''


ACCEPTANCE_TEXT = (
    "# AC-WIDG-001\n"
    "\n"
    "Covers: R-WIDG-001\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given a number is 2\n"
    "When bar_double is invoked with [number]\n"
    "Then value equals 4\n"
    "```\n"
)


def build_fixture(repo_root, expected, log):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widgetry\n"
        "title: Widgetry\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-WIDG]\n"
        "---\n"
        "\n"
        "# Widgetry\n"
        "\n"
        "## Purpose\n\nDoubles numbers.\n\n"
        "## Scope\n\n- In scope: doubling.\n\n"
        "## Definitions\n\nNone.\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n"
        "## Change log\n\n- Initial.\n",
    )
    write(
        comp / "requirements" / "R-WIDG-001.md",
        "**R-WIDG-001** — `bar_double` MUST return twice its argument.\n",
    )
    write(comp / "acceptance" / "AC-WIDG-001.md", ACCEPTANCE_TEXT)
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nbar_double(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "P-WIDG.md",
        "---\n"
        "id: P-WIDG\n"
        "title: Widget doubling\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Widget doubling\n\n## Purpose\n\nDoubling.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    write(
        repo_root / "gen" / SLUG / "widgetry.py",
        "def bar_double(x):\n    return x * 2\n",
    )

    write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        "LOG = " + repr(str(log)) + "\n"
        + "SOURCE = " + repr(emitted_source(expected)) + "\n"
        + COMPILER_BODY,
    )
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        PROBE_SOURCE,
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "CRITERION_TEXT = " + repr(ACCEPTANCE_TEXT) + "\n" + ASSEMBLER_BODY,
    )


@pytest.mark.parametrize(
    "expected, outcome",
    [(4, "pass"), (5, "fail")],
)
def test_compiled_criterion_invokes_mock_compiler_and_reports_result(tmp_path, expected, outcome):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log = tmp_path / "compiler_calls.log"
    build_fixture(repo_root, expected, log)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    assert log.is_file(), "the mock criterion-compiler was never invoked"
    calls = [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert calls, "the mock criterion-compiler was never invoked"
    assert any(CRITERION_ID in line for line in calls), calls

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1, criteria
    assert field(matching[0], "result") == outcome