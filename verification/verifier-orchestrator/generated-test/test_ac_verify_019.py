# hotdocs-criterion: sha256:4f51dbd7548ee4f251862a8fd1e50e8743b228e90371897eaa8e0185916a70e1
import shutil
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FENCE = "```"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def requirement_text(rid):
    return (
        "# " + rid + "\n"
        "\n"
        "**" + rid + "** — `do_the_thing(x)` MUST return a value for " + rid + ".\n"
    )


def acceptance_text(aid, rid):
    return (
        "# " + aid + "\n"
        "\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n"
        "\n"
        + FENCE + "gherkin\n"
        "Given an input x of 1\n"
        "When do_the_thing is called with x\n"
        "Then it returns a value\n"
        + FENCE + "\n"
    )


def characterization_source(second_passes, extra_0031=False):
    src = (
        "def test_ac_foo_001_returns_value():\n"
        "    assert 1 + 1 == 2\n"
        "\n"
        "\n"
        "def test_ac_foo_001_other():\n"
        "    assert 'a' * 2 == 'aa'\n"
        "\n"
        "\n"
        "def test_ac_foo_002_fails():\n"
    )
    if second_passes:
        src += "    assert True\n"
    else:
        src += "    assert 1 == 2\n"
    if extra_0031:
        src += (
            "\n"
            "\n"
            "def test_ac_foo_0031_x():\n"
            "    assert True\n"
        )
    return src


def build_fixture(repo_root, second_passes=False, with_third=False):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Thing** — a thing.\n")
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [pipeline-team]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: pipeline/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Does the thing.\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        + FENCE + "\n"
        "do_the_thing(x) -> int\n"
        + FENCE + "\n"
        "\n"
        "`do_the_thing` returns `x` plus one.\n",
    )
    ids = ["001", "002"] + (["003"] if with_third else [])
    for n in ids:
        rid = "R-FOO-" + n
        aid = "AC-FOO-" + n
        write(comp / "requirements" / (rid + ".md"), requirement_text(rid))
        write(comp / "acceptance" / (aid + ".md"), acceptance_text(aid, rid))
    write(
        repo_root / "pipeline" / "foo" / "foo.py",
        "def do_the_thing(x):\n"
        "    return x + 1\n",
    )
    write(
        repo_root / "verification" / "foo" / "test_foo.py",
        characterization_source(second_passes, extra_0031=with_third),
    )


def criteria_by_id(report):
    return {c["id"]: c for c in field(report, "criteria")}


def summary(report):
    return (
        sorted((c["id"], c["result"]) for c in field(report, "criteria")),
        field(report, "interface_drift"),
        field(report, "mutation_score"),
        field(report, "overall"),
        list(field(report, "assets")),
        list(field(report, "drivers")),
    )


def test_sealed_failing_then_fixed(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, second_passes=False)

    report = verifier_orchestrator.verify("comp-foo", repo_root)
    crit = criteria_by_id(report)
    assert crit["AC-FOO-001"]["result"] == "pass"
    assert crit["AC-FOO-002"]["result"] == "fail"
    assert crit["AC-FOO-002"].get("failure_detail")
    assert field(report, "interface_drift") is False
    assert field(report, "mutation_score") is None
    assert list(field(report, "assets")) == []
    assert list(field(report, "drivers")) == []
    assert field(report, "overall") == "fail"
    assert not (repo_root / "gen" / "foo").exists()

    write(
        repo_root / "verification" / "foo" / "test_foo.py",
        characterization_source(second_passes=True),
    )
    report = verifier_orchestrator.verify("comp-foo", repo_root)
    crit = criteria_by_id(report)
    assert crit["AC-FOO-001"]["result"] == "pass"
    assert crit["AC-FOO-002"]["result"] == "pass"
    assert field(report, "interface_drift") is False
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "pass"


def test_criterion_without_characterization_test(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, second_passes=True, with_third=True)

    report = verifier_orchestrator.verify("comp-foo", repo_root)
    crit = criteria_by_id(report)
    assert crit["AC-FOO-001"]["result"] == "pass"
    assert crit["AC-FOO-002"]["result"] == "pass"
    assert crit["AC-FOO-003"]["result"] == "fail"
    detail = crit["AC-FOO-003"]["failure_detail"]
    assert field(detail, "message") == "no characterization test"
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"


def test_provenance_and_pycache_ignored(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, second_passes=True)

    before = verifier_orchestrator.verify("comp-foo", repo_root)
    assert field(before, "overall") == "pass"

    src = repo_root / "pipeline" / "foo"
    write(
        src / ".sealed-provenance.json",
        '{"owners": ["pipeline-team"], "source_sha256": "sha256:' + "0" * 64 + '", "verdict": "pass"}\n',
    )
    pyc = src / "__pycache__"
    pyc.mkdir(parents=True, exist_ok=True)
    (pyc / "foo.cpython-312.pyc").write_bytes(b"\x00\x01garbage\xff")

    after = verifier_orchestrator.verify("comp-foo", repo_root)
    assert summary(after) == summary(before)
    assert field(after, "overall") == "pass"
    assert field(after, "interface_drift") is False


def test_missing_source_directory_fails(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, second_passes=True)

    shutil.rmtree(repo_root / "pipeline" / "foo")
    report = verifier_orchestrator.verify("comp-foo", repo_root)
    assert field(report, "overall") == "fail"