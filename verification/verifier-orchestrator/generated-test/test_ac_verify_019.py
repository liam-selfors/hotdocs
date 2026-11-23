# hotdocs-criterion: sha256:6c33714035897dd387006c939bbc43c74858f2548de45e151b7d50895104c68f
import shutil
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def characterization_source(fail002, with_003):
    lines = [
        "def test_ac_foo_001_returns_value():",
        "    assert 2 + 2 == 4",
        "",
        "",
        "def test_ac_foo_001_other():",
        "    assert 'a' == 'a'",
        "",
        "",
        "def test_ac_foo_002_fails():",
        "    assert " + ("1 == 2" if fail002 else "1 == 1"),
        "",
    ]
    if with_003:
        lines += [
            "",
            "def test_ac_foo_0031_x():",
            "    assert True",
            "",
        ]
    return "\n".join(lines)


def plant_stand_ins(root):
    assembler = "\n".join([
        "def assemble_criterion(component_id, criterion_id, repo_root):",
        "    return {",
        "        'component_id': component_id,",
        "        'criterion_id': criterion_id,",
        "        'covers': 'R-' + criterion_id[3:],",
        "        'criterion_text': 'text',",
        "        'requirement_text': 'req',",
        "        'interface': 'do_the_thing(x) -> int',",
        "        'glossary': '',",
        "        'dependency_interfaces': {},",
        "        'testing': '',",
        "    }",
        "",
    ])
    write(root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", assembler)
    probe = "\n".join([
        "class _Report:",
        "    def __init__(self):",
        "        self.ok = True",
        "        self.findings = []",
        "        self.tests_run = 0",
        "        self.tests_reached = 0",
        "",
        "    def to_dict(self):",
        "        return {'ok': self.ok, 'findings': list(self.findings),",
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}",
        "",
        "",
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,",
        "          interpreter=None, assets=None):",
        "    return _Report()",
        "",
    ])
    write(root / "gen" / "test-probe" / "test_probe.py", probe)


def build_fixture(root, fail002=True, with_003=False):
    root = Path(root)
    comp = root / "specs" / "components" / "foo"
    write(comp / "component.md", "\n".join([
        "---",
        "id: comp-foo",
        "title: Foo",
        "status: draft",
        "owners: [team-foo]",
        "sealed: true",
        "source_path: pipeline/foo/",
        "---",
        "",
        "# Foo",
        "",
        "## Purpose",
        "",
        "Matches existing behavior; do not regenerate.",
        "",
        "## Scope",
        "",
        "- In scope: do_the_thing.",
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
    ids = ["001", "002"] + (["003"] if with_003 else [])
    for n in ids:
        write(comp / "requirements" / ("R-FOO-" + n + ".md"),
              "# R-FOO-" + n + "\n\n**R-FOO-" + n + "** — do_the_thing MUST return its argument.\n")
        write(comp / "acceptance" / ("AC-FOO-" + n + ".md"), "\n".join([
            "# AC-FOO-" + n,
            "",
            "Covers: R-FOO-" + n,
            "Kind: generated-test",
            "",
            "```gherkin",
            "Given a value x is 1",
            "When do_the_thing is invoked with 1",
            "Then the result is 1",
            "```",
            "",
        ]))
    write(comp / "interface" / "library.md", "\n".join([
        "# Library",
        "",
        "```",
        "do_the_thing(x) -> int",
        "```",
        "",
        "Returns `x` unchanged.",
        "",
    ]))
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(root / "specs" / "glossary.md", "# Glossary\n")
    write(root / "pipeline" / "foo" / "foo.py", "\n".join([
        "def do_the_thing(x):",
        "    return x",
        "",
    ]))
    write(root / "verification" / "foo" / "test_foo.py",
          characterization_source(fail002, with_003))
    plant_stand_ins(root)
    return root


def run_verify(root):
    return verifier_orchestrator.verify("comp-foo", Path(root))


def by_id(report):
    return {field(c, "id"): c for c in field(report, "criteria")}


def detail_message(c):
    fd = c.get("failure_detail") if isinstance(c, dict) else getattr(c, "failure_detail", None)
    if fd is None:
        return None
    return field(fd, "message")


def summarize(report):
    crit = by_id(report)
    return {
        "criteria": {k: (field(v, "result"), detail_message(v)) for k, v in crit.items()},
        "interface_drift": field(report, "interface_drift"),
        "mutation_score": field(report, "mutation_score"),
        "overall": field(report, "overall"),
    }


def test_sealed_one_failing_criterion(tmp_path):
    root = build_fixture(tmp_path / "repo", fail002=True)
    assert not (root / "gen" / "foo").exists()
    report = run_verify(root)
    crit = by_id(report)
    assert field(crit["AC-FOO-001"], "result") == "pass"
    assert field(crit["AC-FOO-002"], "result") == "fail"
    fd = crit["AC-FOO-002"].get("failure_detail") if isinstance(crit["AC-FOO-002"], dict) \
        else getattr(crit["AC-FOO-002"], "failure_detail", None)
    assert fd is not None
    assert field(report, "interface_drift") is False
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"


def test_sealed_all_passing(tmp_path):
    root = build_fixture(tmp_path / "repo", fail002=False)
    report = run_verify(root)
    crit = by_id(report)
    assert field(crit["AC-FOO-001"], "result") == "pass"
    assert field(crit["AC-FOO-002"], "result") == "pass"
    assert field(report, "overall") == "pass"


def test_sealed_criterion_without_test(tmp_path):
    root = build_fixture(tmp_path / "repo", fail002=False, with_003=True)
    report = run_verify(root)
    crit = by_id(report)
    assert field(crit["AC-FOO-001"], "result") == "pass"
    assert field(crit["AC-FOO-002"], "result") == "pass"
    assert field(crit["AC-FOO-003"], "result") == "fail"
    assert detail_message(crit["AC-FOO-003"]) == "no characterization test"
    assert field(report, "overall") == "fail"


def test_sealed_ignores_provenance_and_pycache(tmp_path):
    root = build_fixture(tmp_path / "repo", fail002=True)
    before = summarize(run_verify(root))
    write(root / "pipeline" / "foo" / ".sealed-provenance.json", "{\"bogus\": true}\n")
    cache = root / "pipeline" / "foo" / "__pycache__"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "foo.cpython-312.pyc").write_bytes(b"\x00\x01garbage")
    write(cache / "stray.py", "def broken(:\n")
    after = summarize(run_verify(root))
    assert after == before


def test_sealed_missing_source_dir(tmp_path):
    root = build_fixture(tmp_path / "repo", fail002=False)
    shutil.rmtree(root / "pipeline" / "foo")
    report = run_verify(root)
    assert field(report, "overall") == "fail"