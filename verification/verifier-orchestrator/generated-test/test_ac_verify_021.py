# hotdocs-criterion: sha256:1b574bf217b42b9d5b9f14151a70b07438ea01991672c4c9637edcc61ccd1e42
import json
import shutil
from pathlib import Path

import pytest

import verifier_orchestrator


PASSING_IMPL = "\n".join([
    "class _Result:",
    "    def __init__(self, value):",
    "        self.value = value",
    "",
    "",
    "def add_two(x):",
    "    return _Result(x + 2)",
    "",
])

FAILING_IMPL = "\n".join([
    "class _Result:",
    "    def __init__(self, value):",
    "        self.value = value",
    "",
    "",
    "def add_two(x):",
    "    return _Result(x + 1000)",
    "",
])

ASSEMBLER_SOURCE = "\n".join([
    "def assemble_criterion(component_id, criterion_id, repo_root):",
    "    return {",
    "        'component_id': component_id,",
    "        'criterion_id': criterion_id,",
    "        'covers': 'R-FOO-001',",
    "        'criterion_text': '',",
    "        'requirement_text': '',",
    "        'interface': '',",
    "        'glossary': '',",
    "        'dependency_interfaces': {},",
    "        'testing': '',",
    "    }",
    "",
])

PROBE_SOURCE = "\n".join([
    "class _Report:",
    "    def __init__(self):",
    "        self.ok = True",
    "        self.findings = []",
    "        self.tests_run = 0",
    "        self.tests_reached = 0",
    "",
    "    def to_dict(self):",
    "        return {'ok': True, 'findings': [], 'tests_run': 0, 'tests_reached': 0}",
    "",
    "",
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, **kwargs):",
    "    return _Report()",
    "",
])


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def live_root():
    return (
        Path(verifier_orchestrator.__file__).resolve().parents[1]
        / "spec-bundle-assembler"
    ).resolve().parents[1]


def build_fixture(root, impl_source):
    root.mkdir(parents=True, exist_ok=True)
    comp = root / "specs" / "components" / "foo"
    write(comp / "component.md", "\n".join([
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [test-team]",
        "realizes: [P-FOO]",
        "---",
        "",
        "# Foo",
        "",
        "## Purpose",
        "",
        "Adds two to a number.",
        "",
        "## Scope",
        "",
        "- In scope: adding two.",
        "",
        "## Definitions",
        "",
        "None.",
        "",
        "## Behavior",
        "",
        "See `requirements/`.",
        "",
        "## Interfaces",
        "",
        "See `interface/`.",
        "",
        "## Data",
        "",
        "See `interface/data/`.",
        "",
        "## Acceptance criteria",
        "",
        "See `acceptance/`.",
        "",
        "## Non-functional constraints",
        "",
        "See `constraints.md`.",
        "",
        "## Open questions",
        "",
        "## Change log",
        "",
        "- Initial.",
        "",
    ]))
    write(comp / "requirements" / "R-FOO-001.md", "\n".join([
        "# R-FOO-001",
        "",
        "**R-FOO-001** - `add_two(x)` MUST return an object whose `value` is `x + 2`.",
        "",
    ]))
    write(comp / "interface" / "library.md", "\n".join([
        "# Library",
        "",
        "```",
        "add_two(x) -> Result",
        "```",
        "",
        "Returns an object whose attribute `value` is `x + 2`.",
        "",
    ]))
    write(comp / "acceptance" / "AC-FOO-001.md", "\n".join([
        "# AC-FOO-001",
        "",
        "Covers: R-FOO-001",
        "Kind: compiled",
        "",
        "```gherkin",
        "Given a n is 3",
        "When add_two is invoked with [n]",
        "Then value equals 5",
        "```",
        "",
    ]))
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(root / "specs" / "product" / "foo.md", "\n".join([
        "---",
        "id: P-FOO",
        "title: Foo capability",
        "status: draft",
        "owners: [test-team]",
        "---",
        "",
        "# Foo capability",
        "",
        "## Purpose",
        "",
        "Adding two.",
        "",
    ]))
    write(root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** - a test term.\n")
    write(root / "gen" / "foo" / "foo.py", impl_source)
    write(root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", ASSEMBLER_SOURCE)
    write(root / "gen" / "test-probe" / "test_probe.py", PROBE_SOURCE)
    src = live_root() / "pipeline" / "criterion-compiler"
    dst = root / "pipeline" / "criterion-compiler"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
    return root


def test_passing_component_json_and_text(tmp_path, capsys):
    root = build_fixture(tmp_path / "repo", PASSING_IMPL)
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
    for line in lines[1:]:
        assert line[0] in (" ", "\t")
    assert any(line.strip() == "AC-FOO-001: pass" for line in lines[1:])


def test_failing_component_returns_1(tmp_path, capsys):
    root = build_fixture(tmp_path / "repo", FAILING_IMPL)
    capsys.readouterr()
    code = verifier_orchestrator.main(["comp-foo", "--repo-root=" + str(root)])
    capsys.readouterr()
    assert code == 1


@pytest.mark.parametrize("case", [
    "no-args",
    "bogus-format",
    "unknown-arg",
    "repo-root-last",
    "no-component",
])
def test_usage_errors_return_2(tmp_path, capsys, case):
    root = build_fixture(tmp_path / "repo", PASSING_IMPL)
    if case == "no-args":
        argv = []
    elif case == "bogus-format":
        argv = ["comp-foo", "--repo-root=" + str(root), "--format=bogus"]
    elif case == "unknown-arg":
        argv = ["comp-foo", "--repo-root=" + str(root), "--hotdocs-smoke-unknown"]
    elif case == "repo-root-last":
        argv = ["comp-foo", "--repo-root"]
    else:
        argv = ["comp-nope", "--repo-root=" + str(root)]
    capsys.readouterr()
    code = verifier_orchestrator.main(argv)
    captured = capsys.readouterr()
    assert code == 2
    assert "hotdocs verify-component" in captured.err