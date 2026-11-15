"""AC-VERIFY-019 (Covers: R-VERIFY-017): sealed components are verified
only by their characterization tests, against the code at source_path."""

import json
import shutil
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Foo** \u2014 a test term.\n"

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: true\n"
    "source_path: pipeline/foo/\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)

LIBRARY_MD = "# Library\n\n```\ndo_the_thing(x: int) -> int\n```\n"

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

FOO_PY = (
    "def do_the_thing(x: int) -> int:\n"
    "    return 2 * x\n"
)


def _requirement(n: str) -> str:
    return (
        f"# R-FOO-{n}\n"
        "\n"
        f"**R-FOO-{n}** \u2014 `do_the_thing(x)` MUST return `2 * x`.\n"
    )


def _acceptance(n: str) -> str:
    return (
        f"# AC-FOO-{n}\n"
        "\n"
        f"Covers: R-FOO-{n}\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When do_the_thing(x) is called\n"
        "Then it returns 4\n"
        "```\n"
    )


def _characterization_tests(fix_002: bool, with_003_decoy: bool) -> str:
    expected_002 = 2 if fix_002 else 3
    text = (
        "import foo\n"
        "\n"
        "\n"
        "def test_ac_foo_001_returns_value():\n"
        "    assert foo.do_the_thing(2) == 4\n"
        "\n"
        "\n"
        "def test_ac_foo_001_other():\n"
        "    assert foo.do_the_thing(0) == 0\n"
        "\n"
        "\n"
        "def test_ac_foo_002_fails():\n"
        f"    assert foo.do_the_thing(1) == {expected_002}\n"
    )
    if with_003_decoy:
        text += (
            "\n"
            "\n"
            "def test_ac_foo_0031_x():\n"
            "    assert foo.do_the_thing(3) == 6\n"
        )
    return text


def _build(repo_root: Path, *, fix_002: bool = False, with_003: bool = False) -> None:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    numbers = ["001", "002"] + (["003"] if with_003 else [])
    for n in numbers:
        _write(comp / "requirements" / f"R-FOO-{n}.md", _requirement(n))
        _write(comp / "acceptance" / f"AC-FOO-{n}.md", _acceptance(n))
    _write(repo_root / "pipeline" / "foo" / "foo.py", FOO_PY)
    _write(
        repo_root / "verification" / "foo" / "test_foo.py",
        _characterization_tests(fix_002, with_003),
    )
    assert not (repo_root / "gen" / "foo").exists()


def _by_id(report):
    return {field(c, "id"): c for c in field(report, "criteria")}


def _snapshot(report):
    crit = _by_id(report)
    return (
        field(report, "overall"),
        field(report, "interface_drift"),
        field(report, "mutation_score"),
        sorted(
            (cid, field(c, "result"), bool(c.get("failure_detail")) if isinstance(c, dict) else False)
            for cid, c in crit.items()
        ),
    )


def _add_ignored_files(repo_root: Path) -> None:
    src = repo_root / "pipeline" / "foo"
    _write(
        src / ".sealed-provenance.json",
        json.dumps({"owners": ["team-a"], "source_hash": "sha256:deadbeef"}),
    )
    pycache = src / "__pycache__"
    pycache.mkdir(parents=True, exist_ok=True)
    (pycache / "stale.cpython-312.pyc").write_bytes(b"\x00\x01not-real-bytecode")


def test_sealed_mixed_results_fail_overall(tmp_path):
    repo_root = tmp_path / "repo"
    _build(repo_root)

    report = verifier_orchestrator.verify("comp-foo", repo_root)

    crit = _by_id(report)
    assert field(crit["AC-FOO-001"], "result") == "pass"
    assert field(crit["AC-FOO-002"], "result") == "fail"
    detail = crit["AC-FOO-002"].get("failure_detail") if isinstance(crit["AC-FOO-002"], dict) \
        else getattr(crit["AC-FOO-002"], "failure_detail", None)
    assert detail
    assert field(report, "interface_drift") is False
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"


def test_sealed_all_passing_overall_pass(tmp_path):
    repo_root = tmp_path / "repo"
    _build(repo_root, fix_002=True)

    report = verifier_orchestrator.verify("comp-foo", repo_root)

    crit = _by_id(report)
    assert field(crit["AC-FOO-001"], "result") == "pass"
    assert field(crit["AC-FOO-002"], "result") == "pass"
    assert field(report, "interface_drift") is False
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "pass"


def test_sealed_criterion_without_matching_test_fails(tmp_path):
    repo_root = tmp_path / "repo"
    _build(repo_root, fix_002=True, with_003=True)

    report = verifier_orchestrator.verify("comp-foo", repo_root)

    crit = _by_id(report)
    assert field(crit["AC-FOO-001"], "result") == "pass"
    assert field(crit["AC-FOO-002"], "result") == "pass"
    c3 = crit["AC-FOO-003"]
    assert field(c3, "result") == "fail"
    detail = c3.get("failure_detail") if isinstance(c3, dict) else getattr(c3, "failure_detail", None)
    assert detail
    assert field(detail, "message") == "no characterization test"
    assert field(report, "overall") == "fail"


def test_sealed_provenance_and_pycache_ignored_mixed(tmp_path):
    repo_root = tmp_path / "repo"
    _build(repo_root)

    before = _snapshot(verifier_orchestrator.verify("comp-foo", repo_root))
    _add_ignored_files(repo_root)
    after = _snapshot(verifier_orchestrator.verify("comp-foo", repo_root))

    assert after == before
    assert before[0] == "fail"


def test_sealed_provenance_and_pycache_ignored_passing(tmp_path):
    repo_root = tmp_path / "repo"
    _build(repo_root, fix_002=True)

    before = _snapshot(verifier_orchestrator.verify("comp-foo", repo_root))
    _add_ignored_files(repo_root)
    after = _snapshot(verifier_orchestrator.verify("comp-foo", repo_root))

    assert after == before
    assert before[0] == "pass"
    assert before[1] is False
    assert before[2] is None


def test_sealed_missing_source_path_fails_overall(tmp_path):
    repo_root = tmp_path / "repo"
    _build(repo_root, fix_002=True)
    shutil.rmtree(repo_root / "pipeline" / "foo")
    assert not (repo_root / "pipeline" / "foo").exists()

    report = verifier_orchestrator.verify("comp-foo", repo_root)

    assert field(report, "overall") == "fail"