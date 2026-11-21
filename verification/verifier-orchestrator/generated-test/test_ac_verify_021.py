# hotdocs-criterion: sha256:73f08f88976881c352cd8854d188db3b83dbcc8a4a281aa09de149ca337d911b
import json
import shutil
from pathlib import Path

import pytest

import verifier_orchestrator


FENCE = "`" * 3


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def live_root():
    return (
        Path(verifier_orchestrator.__file__).resolve().parents[1]
        / "spec-bundle-assembler"
    ).resolve().parents[1]


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team]\n"
    "realizes: [P-FOO]\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Doubles a number.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: doubling a number.\n"
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
    "owners: [team]\n"
    "---\n"
    "\n"
    "# Foo capability\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Doubling numbers.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- Doubling.\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    + FENCE + "\n"
    "double_it(x: int) -> object\n"
    + FENCE + "\n"
    "\n"
    "`double_it` returns an object whose attribute `value` is twice `x`.\n"
)

REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** - `double_it(x)` MUST return an object whose `value` is `2 * x`.\n"
)

MODULE_PY = (
    "class _Doubled:\n"
    "    def __init__(self, value):\n"
    "        self.value = value\n"
    "\n"
    "\n"
    "def double_it(x):\n"
    "    return _Doubled(2 * x)\n"
)

PROBE_PY = (
    "class _Report:\n"
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
    "    return _Report()\n"
)

ASSEMBLER_PY = (
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': 'R-FOO-001',\n"
    "        'criterion_text': 'criterion',\n"
    "        'requirement_text': 'requirement',\n"
    "        'interface': 'double_it(x: int) -> object',\n"
    "        'glossary': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'testing': '',\n"
    "    }\n"
)


def acceptance_md(expected):
    return (
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: compiled\n"
        "\n"
        + FENCE + "gherkin\n"
        "Given a n is 2\n"
        "When double_it is invoked with {\"x\": n}\n"
        "Then value equals " + repr(expected) + "\n"
        + FENCE + "\n"
    )


def build_fixture(root, expected):
    comp = root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "acceptance" / "AC-FOO-001.md", acceptance_md(expected))
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(root / "specs" / "product" / "foo.md", PRODUCT_MD)
    write(root / "specs" / "glossary.md", "# Glossary\n\n- **Thing** - a thing.\n")
    write(root / "gen" / "foo" / "foo.py", MODULE_PY)
    write(root / "gen" / "test-probe" / "test_probe.py", PROBE_PY)
    write(
        root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        ASSEMBLER_PY,
    )
    src = live_root() / "pipeline" / "criterion-compiler"
    dst = root / "pipeline" / "criterion-compiler"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
    return root


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_passing_component_json_and_text(tmp_path, capsys):
    root = build_fixture(tmp_path / "repo", 4)
    capsys.readouterr()

    code = verifier_orchestrator.main(
        ["comp-foo", "--repo-root=" + str(root), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0
    report = json.loads(out)
    assert report["overall"] == "pass"

    code = verifier_orchestrator.main(
        ["comp-foo", "--repo-root", str(root), "--format", "text"]
    )
    out = capsys.readouterr().out
    assert code == 0
    lines = [line for line in out.splitlines() if line.strip()]
    assert lines[0] == "comp-foo: pass"
    assert len(lines) >= 2
    criterion_lines = lines[1:]
    for line in criterion_lines:
        assert line[0] in (" ", "\t")
    assert "AC-FOO-001: pass" in [line.strip() for line in criterion_lines]


def test_failing_component_returns_1(tmp_path, capsys):
    root = build_fixture(tmp_path / "repo", 5)
    capsys.readouterr()
    code = verifier_orchestrator.main(["comp-foo", "--repo-root=" + str(root)])
    capsys.readouterr()
    assert code == 1


def test_usage_errors_return_2(tmp_path, capsys):
    root = tmp_path / "repo"
    write(root / "specs" / "components" / "foo" / "component.md", COMPONENT_MD)
    cases = [
        [],
        ["comp-foo", "--repo-root=" + str(root), "--format=bogus"],
        ["comp-foo", "--repo-root=" + str(root), "--hotdocs-smoke-unknown"],
        ["comp-foo", "--repo-root"],
        ["comp-nope", "--repo-root=" + str(root)],
    ]
    capsys.readouterr()
    for argv in cases:
        code = verifier_orchestrator.main(list(argv))
        captured = capsys.readouterr()
        assert code == 2, argv
        assert "hotdocs verify-component" in captured.err, argv