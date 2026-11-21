# hotdocs-criterion: sha256:7799d0bd4aed1afdd899f9cbd0519018b9ec698c114dfe572cb5ad00257a4665
import json
from pathlib import Path

import pytest

import verifier_orchestrator


COMPONENT_ID = "comp-widget-calc"
SLUG = "widget-calc"
MODULE = "widget_calc"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def compiled_test_source(expected):
    return (
        "import " + MODULE + "\n"
        "\n"
        "\n"
        "def test_ac_widget_001():\n"
        "    result = " + MODULE + ".calc_value()\n"
        "    assert result == " + repr(expected) + "\n"
    )


def compiler_source(log_path, test_source):
    return (
        "import os\n"
        "from dataclasses import dataclass, field\n"
        "from pathlib import Path\n"
        "\n"
        "GATE_VERSION = 'criterion-compiler@1.0.0'\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
        "_SOURCE = " + repr(test_source) + "\n"
        "_CRITERION_ID = " + repr(CRITERION_ID) + "\n"
        "_COVERS = " + repr(REQUIREMENT_ID) + "\n"
        "_SLUG = " + repr(SLUG) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class ParsedCriterion:\n"
        "    criterion_id: str = ''\n"
        "    covers: str = ''\n"
        "    kind: str = ''\n"
        "    gherkin: str = ''\n"
        "    file: str = ''\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class InterfaceSurface:\n"
        "    functions: dict = field(default_factory=dict)\n"
        "    types: dict = field(default_factory=dict)\n"
        "    module_name: str = ''\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class CompileReport:\n"
        "    outputs: list = field(default_factory=list)\n"
        "    gate_version: str = GATE_VERSION\n"
        "    summary: dict = field(default_factory=dict)\n"
        "\n"
        "\n"
        "def compile(component_id, repo_root, target='pytest', out_dir=None):\n"
        "    repo_root = Path(repo_root)\n"
        "    _log('compile ' + str(component_id) + ' ' + _CRITERION_ID)\n"
        "    if out_dir is None:\n"
        "        out_dir = repo_root / 'verification' / _SLUG / 'compiled'\n"
        "    out_dir = Path(out_dir)\n"
        "    if not out_dir.is_absolute():\n"
        "        out_dir = repo_root / out_dir\n"
        "    out_dir.mkdir(parents=True, exist_ok=True)\n"
        "    target_file = out_dir / ('test_' + _CRITERION_ID.lower().replace('-', '_') + '.py')\n"
        "    target_file.write_text(_SOURCE, encoding='utf-8')\n"
        "    try:\n"
        "        rel = str(target_file.resolve().relative_to(repo_root.resolve()))\n"
        "    except ValueError:\n"
        "        rel = str(target_file.resolve())\n"
        "    outputs = [{'criterion_id': _CRITERION_ID, 'covers': _COVERS,\n"
        "                'status': 'compiled', 'file': rel}]\n"
        "    return CompileReport(outputs=outputs, gate_version=GATE_VERSION,\n"
        "                         summary={'compiled': 1, 'errors': 0,\n"
        "                                  'skipped_non_compiled_kind': 0})\n"
        "\n"
        "\n"
        "def compile_criterion(criterion, surface=None):\n"
        "    if isinstance(criterion, dict):\n"
        "        cid = criterion.get('criterion_id')\n"
        "    else:\n"
        "        cid = getattr(criterion, 'criterion_id', None)\n"
        "    _log('compile_criterion ' + str(cid))\n"
        "    return {'status': 'compiled', 'source': _SOURCE}\n"
        "\n"
        "\n"
        "def main(argv=None):\n"
        "    return 0\n"
    )


def assembler_source():
    bundle = {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQUIREMENT_ID,
        "criterion_text": "Given a seed is 1\nWhen calc_value is invoked with []\nThen result equals 7\n",
        "requirement_text": "calc_value MUST return 7.",
        "interface": "calc_value() -> int",
        "glossary": "# Glossary",
        "dependency_interfaces": {},
        "testing": "",
    }
    return (
        "BUNDLE = " + repr(bundle) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    b = dict(BUNDLE)\n"
        "    b['component_id'] = component_id\n"
        "    b['criterion_id'] = criterion_id\n"
        "    return b\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    raise RuntimeError('assemble is not used by verify')\n"
    )


def probe_source():
    return (
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
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
        "    return ProbeReport()\n"
    )


def build_fixture(repo_root, log_path, expected):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget Calc\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget Calc\n"
        "\n"
        "## Purpose\n\nComputes a widget value.\n\n"
        "## Scope\n\n- In scope: calc_value.\n\n"
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
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "# " + REQUIREMENT_ID + "\n\n**" + REQUIREMENT_ID + "** — `calc_value` MUST return 7.\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a seed is 1\n"
        "When calc_value is invoked with []\n"
        "Then result equals 7\n"
        "```\n",
    )
    write(comp / "interface" / "library.md", "# Library\n\n```\ncalc_value() -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Widget\n\n## Purpose\n\nWidgets.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** — a thing.\n")
    write(repo_root / "gen" / SLUG / (MODULE + ".py"), "def calc_value():\n    return 7\n")
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source())
    write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        compiler_source(log_path, compiled_test_source(expected)),
    )


@pytest.mark.parametrize("expected_value, expected_result", [(7, "pass"), (8, "fail")])
def test_compiled_criterion_dispatched_to_compiler_and_reported(tmp_path, expected_value, expected_result):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "compiler_calls.log"
    build_fixture(repo_root, log_path, expected_value)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    assert log_path.is_file(), "mock criterion-compiler was never invoked"
    calls = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert calls, "mock criterion-compiler was never invoked"
    assert any(CRITERION_ID in line for line in calls), calls

    criteria = list(field(report, "criteria"))
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1, criteria
    entry = matching[0]
    assert field(entry, "result") in ("pass", "fail")
    assert field(entry, "result") == expected_result, entry