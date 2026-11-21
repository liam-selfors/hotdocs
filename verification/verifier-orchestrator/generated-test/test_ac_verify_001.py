# hotdocs-criterion: sha256:7114fc62c3bf213c945c291e546ad38c31b4e01793d3217e3210af939006c12e
import json
from pathlib import Path

import pytest

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"

COMPILED_TEST_SOURCE = (
    "import widget\n"
    "\n"
    "\n"
    "def test_widget_add():\n"
    "    assert widget.widget_add(2) == 3\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_corpus(repo_root, impl_source):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** - a thing that adds.\n",
    )
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Adds numbers.\n",
    )
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Adds one to a number.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: adding.\n"
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
        "# R-WIDGET-001\n"
        "\n"
        "**R-WIDGET-001** - `widget_add(x)` MUST return `x + 1`.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "widget_add(x: int) -> int\n"
        "```\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a value is 2\n"
        "When widget_add is invoked with [value]\n"
        "Then total equals 3\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "gen" / SLUG / "widget.py", impl_source)


def plant_compiler(repo_root, log_path):
    source = "\n".join([
        "from pathlib import Path",
        "",
        "GATE_VERSION = 'criterion-compiler@1.0.0'",
        "LOG_PATH = " + repr(str(log_path)),
        "TEST_SOURCE = " + repr(COMPILED_TEST_SOURCE),
        "CRITERION_ID = " + repr(CRITERION_ID),
        "COVERS = " + repr(REQUIREMENT_ID),
        "",
        "",
        "class ParsedCriterion:",
        "    def __init__(self, criterion_id='', covers='', kind='', gherkin='', file=''):",
        "        self.criterion_id = criterion_id",
        "        self.covers = covers",
        "        self.kind = kind",
        "        self.gherkin = gherkin",
        "        self.file = file",
        "",
        "",
        "class InterfaceSurface:",
        "    def __init__(self, functions=None, types=None, module_name=''):",
        "        self.functions = functions if functions is not None else {}",
        "        self.types = types if types is not None else {}",
        "        self.module_name = module_name",
        "",
        "",
        "class CompileReport:",
        "    def __init__(self, outputs, gate_version, summary):",
        "        self.outputs = outputs",
        "        self.gate_version = gate_version",
        "        self.summary = summary",
        "",
        "    def to_dict(self):",
        "        return {'outputs': self.outputs, 'gate_version': self.gate_version, 'summary': self.summary}",
        "",
        "",
        "def _log(line):",
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:",
        "        fh.write(line + '\\n')",
        "",
        "",
        "def _get(value, name):",
        "    if isinstance(value, dict):",
        "        return value.get(name)",
        "    return getattr(value, name, None)",
        "",
        "",
        "def compile(component_id, repo_root, target='pytest', out_dir=None):",
        "    repo_root = Path(repo_root)",
        "    slug = component_id[5:] if component_id.startswith('comp-') else component_id",
        "    if out_dir is None:",
        "        out = repo_root / 'verification' / slug / 'compiled'",
        "    else:",
        "        out = Path(out_dir)",
        "        if not out.is_absolute():",
        "            out = repo_root / out",
        "    out.mkdir(parents=True, exist_ok=True)",
        "    target_file = out / ('test_' + CRITERION_ID.lower().replace('-', '_') + '.py')",
        "    target_file.write_text(TEST_SOURCE, encoding='utf-8')",
        "    _log('compile ' + str(component_id) + ' ' + CRITERION_ID)",
        "    try:",
        "        rel = target_file.resolve().relative_to(repo_root.resolve()).as_posix()",
        "    except ValueError:",
        "        rel = str(target_file.resolve())",
        "    outputs = [{'criterion_id': CRITERION_ID, 'covers': COVERS, 'status': 'compiled', 'file': rel}]",
        "    summary = {'compiled': 1, 'errors': 0, 'skipped_non_compiled_kind': 0}",
        "    return CompileReport(outputs, GATE_VERSION, summary)",
        "",
        "",
        "def compile_criterion(criterion, surface=None):",
        "    _log('compile_criterion ' + str(_get(criterion, 'criterion_id')))",
        "    return {'status': 'compiled', 'source': TEST_SOURCE}",
        "",
    ])
    write(repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py", source)


def plant_assembler(repo_root):
    source = "\n".join([
        "def assemble_criterion(component_id, criterion_id, repo_root):",
        "    return {",
        "        'component_id': component_id,",
        "        'criterion_id': criterion_id,",
        "        'covers': " + repr(REQUIREMENT_ID) + ",",
        "        'criterion_text': 'Given a value is 2',",
        "        'requirement_text': 'widget_add(x) MUST return x + 1.',",
        "        'interface': 'widget_add(x: int) -> int',",
        "        'glossary': '',",
        "        'dependency_interfaces': {},",
        "        'testing': '',",
        "    }",
        "",
    ])
    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", source)


def plant_probe(repo_root):
    source = "\n".join([
        "GATE_VERSION = 'test-probe@1.3.0'",
        "",
        "",
        "class ProbeReport:",
        "    def __init__(self):",
        "        self.ok = True",
        "        self.findings = []",
        "        self.tests_run = 1",
        "        self.tests_reached = 1",
        "",
        "    def to_dict(self):",
        "        return {'ok': self.ok, 'findings': list(self.findings),",
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}",
        "",
        "",
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):",
        "    return ProbeReport()",
        "",
    ])
    write(repo_root / "gen" / "test-probe" / "test_probe.py", source)


def build_fixture(repo_root, impl_source):
    log_path = repo_root / "compiler_calls.log"
    build_corpus(repo_root, impl_source)
    plant_compiler(repo_root, log_path)
    plant_assembler(repo_root)
    plant_probe(repo_root)
    return log_path


def find_criterion(report, criterion_id):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == criterion_id]
    assert len(matches) == 1, "criteria: " + repr(criteria)
    return matches[0]


@pytest.mark.parametrize(
    "impl_source, expected",
    [
        ("def widget_add(x):\n    return x + 1\n", "pass"),
        ("def widget_add(x):\n    return x + 100\n", "fail"),
    ],
)
def test_compiled_criterion_dispatched_to_compiler_and_reported(tmp_path, impl_source, expected):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = build_fixture(repo_root, impl_source)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    assert log_path.is_file(), "mock criterion-compiler was never invoked"
    log_text = log_path.read_text(encoding="utf-8")
    assert CRITERION_ID in log_text, "compiler log: " + repr(log_text)

    entry = find_criterion(report, CRITERION_ID)
    assert field(entry, "kind") == "compiled"
    assert field(entry, "result") == expected

    as_dict = report.to_dict()
    json.dumps(as_dict)
    dict_entries = [c for c in as_dict["criteria"] if c["id"] == CRITERION_ID]
    assert len(dict_entries) == 1
    assert dict_entries[0]["result"] == expected