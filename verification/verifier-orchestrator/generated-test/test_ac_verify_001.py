# hotdocs-criterion: sha256:9e42450f51ba0ab5f53b765f5d6c4ff768f24f440e5fb1675bc34117c4a5ec1f
import json
from pathlib import Path

import pytest

import verifier_orchestrator


SLUG = "foo-thing"
COMPONENT_ID = "comp-foo-thing"
CRITERION_ID = "AC-FOOT-001"
REQUIREMENT_ID = "R-FOOT-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def compiler_source(log_path, passing):
    lines = [
        "import json",
        "from dataclasses import dataclass, field",
        "from pathlib import Path",
        "",
        "LOG = " + repr(str(log_path)),
        "PASSING = " + repr(bool(passing)),
        "CRITERION_ID = " + repr(CRITERION_ID),
        "COVERS = " + repr(REQUIREMENT_ID),
        "SLUG = " + repr(SLUG),
        "GATE_VERSION = " + repr("criterion-compiler@1.0.0"),
        "",
        "",
        "@dataclass",
        "class ParsedCriterion:",
        "    criterion_id: str",
        "    covers: str",
        "    kind: str",
        "    gherkin: str",
        "    file: str",
        "",
        "",
        "@dataclass",
        "class InterfaceSurface:",
        "    functions: dict = field(default_factory=dict)",
        "    types: dict = field(default_factory=dict)",
        "    module_name: str = ''",
        "",
        "",
        "@dataclass",
        "class CompileReport:",
        "    outputs: list",
        "    gate_version: str",
        "    summary: dict",
        "",
        "    def to_dict(self):",
        "        return {'outputs': self.outputs, 'gate_version': self.gate_version, 'summary': self.summary}",
        "",
        "",
        "def _log(line):",
        "    with open(LOG, 'a', encoding='utf-8') as fh:",
        "        fh.write(line + '\\n')",
        "",
        "",
        "def _source():",
        "    expected = 3 if PASSING else 5",
        "    return ('import foo_thing\\n\\n\\n'",
        "            'def test_ac_foot_001():\\n'",
        "            '    assert foo_thing.bar_value() == ' + repr(expected) + '\\n')",
        "",
        "",
        "def compile(component_id, repo_root, target='pytest', out_dir=None):",
        "    _log('compile ' + str(component_id))",
        "    root = Path(repo_root)",
        "    out = Path(out_dir) if out_dir is not None else root / 'verification' / SLUG / 'compiled'",
        "    out.mkdir(parents=True, exist_ok=True)",
        "    path = out / 'test_ac_foot_001.py'",
        "    path.write_text(_source(), encoding='utf-8')",
        "    try:",
        "        rel = str(path.resolve().relative_to(root.resolve()))",
        "    except ValueError:",
        "        rel = str(path.resolve())",
        "    return CompileReport(",
        "        outputs=[{'criterion_id': CRITERION_ID, 'covers': COVERS, 'status': 'compiled', 'file': rel}],",
        "        gate_version=GATE_VERSION,",
        "        summary={'compiled': 1, 'errors': 0, 'skipped_non_compiled_kind': 0},",
        "    )",
        "",
        "",
        "def compile_criterion(criterion, surface=None):",
        "    cid = criterion['criterion_id'] if isinstance(criterion, dict) else getattr(criterion, 'criterion_id', '')",
        "    _log('compile_criterion ' + str(cid))",
        "    return {'status': 'compiled', 'source': _source()}",
        "",
        "",
        "def main(argv=None):",
        "    return 0",
        "",
    ]
    return "\n".join(lines)


def probe_source():
    lines = [
        "class _Report:",
        "    def __init__(self):",
        "        self.ok = True",
        "        self.findings = []",
        "",
        "    def to_dict(self):",
        "        return {'ok': self.ok, 'findings': list(self.findings)}",
        "",
        "",
        "def probe(test_source, criterion_bundle, module_name, **kwargs):",
        "    return _Report()",
        "",
    ]
    return "\n".join(lines)


def build_fixture(repo_root, log_path, passing):
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Foo Thing\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "realizes: [P-FOO-THING]\n"
        "---\n"
        "\n"
        "# Foo Thing\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Returns a fixed value.\n",
    )
    write(
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "# " + REQUIREMENT_ID + "\n"
        "\n"
        "**" + REQUIREMENT_ID + "** \u2014 `bar_value()` MUST return 3.\n",
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
        "When bar_value is invoked with []\n"
        "Then value equals 3\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "bar_value() -> int\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "foo-capability.md",
        "---\n"
        "id: P-FOO-THING\n"
        "title: Foo Capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Foo Capability\n"
        "\n"
        "Provides a fixed value.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** \u2014 a thing.\n")
    write(
        repo_root / "gen" / SLUG / "foo_thing.py",
        "def bar_value():\n    return 3\n",
    )
    write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        compiler_source(log_path, passing),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source())


@pytest.mark.parametrize("passing,expected", [(True, "pass"), (False, "fail")])
def test_compiled_criterion_invokes_mock_compiler_and_reports_result(tmp_path, passing, expected):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "compiler_calls.log"
    build_fixture(repo_root, log_path, passing)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    # The mock compiler was invoked for that criterion.
    assert log_path.is_file(), "mock criterion-compiler was never invoked"
    calls = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert calls, "mock criterion-compiler was never invoked"
    relevant = [
        c for c in calls
        if c == "compile " + COMPONENT_ID or c == "compile_criterion " + CRITERION_ID
    ]
    assert relevant, "mock compiler calls did not concern the criterion: " + repr(calls)

    # Its pass/fail result appears in the report under that criterion's id.
    criteria = field(report, "criteria")
    entries = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(entries) == 1, "criterion missing from report: " + json.dumps(
        [field(c, "id") for c in criteria]
    )
    entry = entries[0]
    assert field(entry, "kind") == "compiled"
    assert field(entry, "covers") == REQUIREMENT_ID
    assert field(entry, "result") == expected