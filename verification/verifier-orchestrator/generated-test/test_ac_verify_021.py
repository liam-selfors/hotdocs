# hotdocs-criterion: sha256:c669e72eb809d7dbda7e31c7a6140133c08418bc006852b5fde9cb07dc531264
import json
import re
import shutil
from pathlib import Path

import verifier_orchestrator


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [test-team]\n"
    "depends_on: []\n"
    "realizes: [P-FOO]\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Adds one to a number.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: adding one.\n"
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
    "- Initial draft.\n"
)

PRODUCT_MD = (
    "---\n"
    "id: P-FOO\n"
    "title: Foo capability\n"
    "status: draft\n"
    "owners: [test-team]\n"
    "---\n"
    "\n"
    "# Foo capability\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Adding one.\n"
)

REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** - `add_one(x)` MUST return a `Result` whose `value` is `x + 1`.\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "add_one(x: int) -> Result\n"
    "```\n"
)

RESULT_MD = (
    "# `Result`\n"
    "\n"
    "```json\n"
    "{\"value\": 3}\n"
    "```\n"
)

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given a n is 2\n"
    "When add_one is invoked with [n]\n"
    "Then value equals 3\n"
    "```\n"
)

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

GLOSSARY_MD = "# Glossary\n\n- **Foo** - a test term.\n"


def module_source(increment):
    return (
        "import dataclasses as _dc\n"
        "\n"
        "\n"
        "@_dc.dataclass\n"
        "class Result:\n"
        "    value: int\n"
        "\n"
        "\n"
        "def add_one(x):\n"
        "    return Result(value=x + " + repr(increment) + ")\n"
    )


ASSEMBLER_SOURCE = (
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': 'R-FOO-001',\n"
    "        'criterion_text': 'criterion text',\n"
    "        'requirement_text': 'requirement text',\n"
    "        'interface': 'add_one(x: int) -> Result',\n"
    "        'glossary': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'testing': '',\n"
    "    }\n"
)

PROBE_SOURCE = (
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
    "GATE_VERSION = 'test-probe@1.3.0'\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
    "    return ProbeReport()\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def live_root():
    return (
        Path(verifier_orchestrator.__file__).resolve().parents[1] / "spec-bundle-assembler"
    ).resolve().parents[1]


def build_fixture(root, increment):
    comp = root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "interface" / "data" / "Result.md", RESULT_MD)
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    write(comp / "constraints.md", CONSTRAINTS_MD)
    write(root / "specs" / "product" / "foo.md", PRODUCT_MD)
    write(root / "specs" / "glossary.md", GLOSSARY_MD)
    write(root / "gen" / "foo" / "foo.py", module_source(increment))
    write(root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", ASSEMBLER_SOURCE)
    write(root / "gen" / "test-probe" / "test_probe.py", PROBE_SOURCE)
    src = live_root() / "pipeline" / "criterion-compiler"
    dst = root / "pipeline" / "criterion-compiler"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
    return root


def test_passing_component_json_and_text(tmp_path, capsys):
    root = build_fixture(tmp_path / "pass", 1)
    capsys.readouterr()

    code = verifier_orchestrator.main(
        ["comp-foo", "--repo-root=" + str(root), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0
    report = json.loads(out)
    assert report["overall"] == "pass"
    ids = [c["id"] for c in report["criteria"]]
    assert "AC-FOO-001" in ids

    code = verifier_orchestrator.main(
        ["comp-foo", "--repo-root", str(root), "--format", "text"]
    )
    out = capsys.readouterr().out
    assert code == 0
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines[0] == "comp-foo: pass"
    criterion_lines = lines[1:]
    assert criterion_lines
    for line in criterion_lines:
        assert line[0].isspace()
    assert "AC-FOO-001: pass" in [line.strip() for line in criterion_lines]


def test_failing_component_returns_1(tmp_path, capsys):
    root = build_fixture(tmp_path / "fail", 2)
    capsys.readouterr()
    code = verifier_orchestrator.main(["comp-foo", "--repo-root=" + str(root)])
    capsys.readouterr()
    assert code == 1


def test_usage_errors_return_2(tmp_path, capsys):
    root = build_fixture(tmp_path / "usage", 1)
    capsys.readouterr()
    cases = [
        [],
        ["comp-foo", "--repo-root=" + str(root), "--format=bogus"],
        ["comp-foo", "--repo-root=" + str(root), "--hotdocs-smoke-unknown"],
        ["comp-foo", "--repo-root"],
        ["comp-nope", "--repo-root=" + str(root)],
    ]
    for argv in cases:
        code = verifier_orchestrator.main(argv)
        captured = capsys.readouterr()
        assert code == 2, argv
        assert "hotdocs verify-component" in captured.err, argv
        assert re.search(r"hotdocs verify(?!-component)", captured.err) is None, argv