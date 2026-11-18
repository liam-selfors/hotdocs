# hotdocs-criterion: sha256:d0050b780a8b488b795e651f297b9d94a7fcb865b2b613649f7938af60c12c75
import importlib.util
import sys
from pathlib import Path

import pytest

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# The test the mock criterion-compiler "emits" for the compiled criterion.
# It imports the component's real module by its underscored slug, as
# criterion-compiler's emitted code does (R-COMPILE-013).
EMITTED_SOURCE = (
    "import widget\n"
    "\n"
    "\n"
    "def test_ac_widget_001():\n"
    "    result = widget.double(2)\n"
    "    assert result == 4\n"
)


def compiler_source(log_path):
    return (
        "import json\n"
        "from dataclasses import dataclass, field\n"
        "from pathlib import Path\n"
        "\n"
        "GATE_VERSION = 'criterion-compiler@1.0.0'\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "SOURCE = " + repr(EMITTED_SOURCE) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
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
        "def _test_name(criterion_id):\n"
        "    return 'test_' + criterion_id.lower().replace('-', '_') + '.py'\n"
        "\n"
        "\n"
        "def _covers(text):\n"
        "    for line in text.splitlines():\n"
        "        if line.startswith('Covers:'):\n"
        "            return line[len('Covers:'):].strip()\n"
        "    return ''\n"
        "\n"
        "\n"
        "def compile_criterion(criterion, surface=None):\n"
        "    if isinstance(criterion, dict):\n"
        "        cid = criterion.get('criterion_id', '')\n"
        "    else:\n"
        "        cid = getattr(criterion, 'criterion_id', '')\n"
        "    _log('compile_criterion ' + str(cid))\n"
        "    return {'status': 'compiled', 'source': SOURCE}\n"
        "\n"
        "\n"
        "def compile(component_id, repo_root, target='pytest', out_dir=None):\n"
        "    repo_root = Path(repo_root)\n"
        "    slug = component_id[5:] if component_id.startswith('comp-') else component_id\n"
        "    out = Path(out_dir) if out_dir is not None else repo_root / 'verification' / slug / 'compiled'\n"
        "    out.mkdir(parents=True, exist_ok=True)\n"
        "    acceptance = repo_root / 'specs' / 'components' / slug / 'acceptance'\n"
        "    outputs = []\n"
        "    skipped = 0\n"
        "    for path in sorted(acceptance.glob('AC-*.md')):\n"
        "        text = path.read_text(encoding='utf-8')\n"
        "        if 'Kind: compiled' not in text:\n"
        "            skipped += 1\n"
        "            continue\n"
        "        cid = path.stem\n"
        "        _log('compile ' + str(component_id) + ' ' + cid)\n"
        "        target_file = out / _test_name(cid)\n"
        "        target_file.write_text(SOURCE, encoding='utf-8')\n"
        "        try:\n"
        "            rel = str(target_file.resolve().relative_to(repo_root.resolve()))\n"
        "        except ValueError:\n"
        "            rel = str(target_file.resolve())\n"
        "        outputs.append({\n"
        "            'criterion_id': cid,\n"
        "            'covers': _covers(text),\n"
        "            'status': 'compiled',\n"
        "            'file': rel,\n"
        "        })\n"
        "    if not outputs:\n"
        "        _log('compile ' + str(component_id))\n"
        "    return CompileReport(\n"
        "        outputs=outputs,\n"
        "        gate_version=GATE_VERSION,\n"
        "        summary={'compiled': len(outputs), 'errors': 0, 'skipped_non_compiled_kind': skipped},\n"
        "    )\n"
    )


def assembler_source(log_path):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('assemble_criterion ' + str(criterion_id) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(REQUIREMENT_ID) + ",\n"
        "        'criterion_text': 'criterion text',\n"
        "        'requirement_text': 'requirement text',\n"
        "        'interface': 'double(x: int) -> int',\n"
        "        'glossary': '',\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )


def build_fixture(repo_root, compiler_log, assembler_log, impl_body):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "widget.md",
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
        "Doubling numbers.\n",
    )
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget doubles a number.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
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
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "# " + REQUIREMENT_ID + "\n\n**" + REQUIREMENT_ID
        + "** — `double(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a n is 2\n"
        "When double is invoked with [n]\n"
        "Then value equals 4\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(
        repo_root / "gen" / SLUG / "widget.py",
        "def double(x):\n" + impl_body,
    )
    write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        compiler_source(compiler_log),
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(assembler_log),
    )


@pytest.mark.parametrize(
    "impl_body, expected",
    [
        ("    return 2 * x\n", "pass"),
        ("    return 2 * x + 1\n", "fail"),
    ],
)
def test_compiled_criterion_dispatched_to_mock_compiler_and_reported(
    tmp_path, impl_body, expected
):
    repo_root = tmp_path / "repo"
    compiler_log = tmp_path / "compiler-calls.log"
    assembler_log = tmp_path / "assembler-calls.log"
    build_fixture(repo_root, compiler_log, assembler_log, impl_body)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    # The mock compiler was invoked for that criterion.
    assert compiler_log.is_file(), "mock criterion-compiler was never invoked"
    lines = [
        line for line in compiler_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(CRITERION_ID in line for line in lines), lines

    # Its pass/fail result appears in the report under that criterion's id.
    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1, criteria
    entry = matching[0]
    assert field(entry, "kind") == "compiled"
    assert field(entry, "result") == expected