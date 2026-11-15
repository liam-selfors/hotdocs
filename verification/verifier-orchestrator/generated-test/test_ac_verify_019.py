"""AC-VERIFY-019 (Covers: R-VERIFY-017): sealed components are verified only by
their characterization tests in verification/<slug>/, against the code at
<repo_root>/<source_path>."""

import importlib.util
import json
import py_compile
import shutil
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Foo** — a test term.\n"

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
    "Foo does the thing to a number.\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "do_the_thing(x: int) -> int\n"
    "```\n"
)

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

FOO_PY = (
    "def do_the_thing(x: int) -> int:\n"
    "    return 2 * x\n"
)

REQUIREMENTS = {
    "R-FOO-001": "`do_the_thing(x)` MUST return `2 * x`.",
    "R-FOO-002": "`do_the_thing(x)` MUST NOT raise for an integer `x`.",
    "R-FOO-003": "`do_the_thing(x)` MUST return an integer.",
}

PASSING_001 = (
    "def test_ac_foo_001_returns_value():\n"
    "    assert 2 * 2 == 4\n"
    "\n"
    "\n"
    "def test_ac_foo_001_other():\n"
    "    assert 0 * 2 == 0\n"
)

FAILING_002 = (
    "\n"
    "\n"
    "def test_ac_foo_002_fails():\n"
    "    assert 3 * 2 == 7\n"
)

FIXED_002 = (
    "\n"
    "\n"
    "def test_ac_foo_002_fails():\n"
    "    assert 3 * 2 == 6\n"
)

DECOY_003 = (
    "\n"
    "\n"
    "def test_ac_foo_0031_x():\n"
    "    assert True\n"
)


def _criterion(ac_id: str, r_id: str) -> str:
    return (
        f"# {ac_id}\n"
        "\n"
        f"Covers: {r_id}\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given an integer x is 2\n"
        "When do_the_thing(x) is called\n"
        "Then it returns 4\n"
        "```\n"
    )


def build(repo_root: Path, test_src: str, criteria=("001", "002")) -> Path:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    for n in criteria:
        r_id = f"R-FOO-{n}"
        ac_id = f"AC-FOO-{n}"
        _write(comp / "requirements" / f"{r_id}.md",
               f"# {r_id}\n\n**{r_id}** — {REQUIREMENTS[r_id]}\n")
        _write(comp / "acceptance" / f"{ac_id}.md", _criterion(ac_id, r_id))
    _write(repo_root / "pipeline" / "foo" / "foo.py", FOO_PY)
    _write(repo_root / "verification" / "foo" / "test_foo.py", test_src)
    return repo_root


def by_id(report):
    return {field(c, "id"): c for c in field(report, "criteria")}


def summary(report):
    crit = {
        cid: (field(c, "result"), field(c, "kind"), field(c, "covers"))
        for cid, c in by_id(report).items()
    }
    return (
        crit,
        field(report, "interface_drift"),
        field(report, "mutation_score"),
        field(report, "overall"),
    )


def test_sealed_component_mixed_results(tmp_path):
    repo = build(tmp_path / "repo", PASSING_001 + FAILING_002)
    assert not (repo / "gen" / "foo").exists()

    report = verifier_orchestrator.verify("comp-foo", repo)
    crit = by_id(report)

    assert field(crit["AC-FOO-001"], "result") == "pass"
    c2 = crit["AC-FOO-002"]
    assert field(c2, "result") == "fail"
    fd = c2.get("failure_detail") if isinstance(c2, dict) else getattr(c2, "failure_detail", None)
    assert fd, "failing criterion must carry a failure_detail"
    assert field(report, "interface_drift") is False
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"


def test_sealed_component_all_passing(tmp_path):
    repo = build(tmp_path / "repo", PASSING_001 + FIXED_002)

    report = verifier_orchestrator.verify("comp-foo", repo)
    crit = by_id(report)

    assert field(crit["AC-FOO-001"], "result") == "pass"
    assert field(crit["AC-FOO-002"], "result") == "pass"
    assert field(report, "interface_drift") is False
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "pass"


def test_criterion_without_characterization_test(tmp_path):
    repo = build(
        tmp_path / "repo",
        PASSING_001 + FIXED_002 + DECOY_003,
        criteria=("001", "002", "003"),
    )

    report = verifier_orchestrator.verify("comp-foo", repo)
    crit = by_id(report)

    c3 = crit["AC-FOO-003"]
    assert field(c3, "result") == "fail"
    fd = c3.get("failure_detail") if isinstance(c3, dict) else getattr(c3, "failure_detail", None)
    assert fd is not None
    assert field(fd, "message") == "no characterization test"
    assert field(crit["AC-FOO-001"], "result") == "pass"
    assert field(crit["AC-FOO-002"], "result") == "pass"
    assert field(report, "overall") == "fail"


def test_provenance_and_pycache_are_ignored(tmp_path):
    repo = build(tmp_path / "repo", PASSING_001 + FAILING_002)

    before = summary(verifier_orchestrator.verify("comp-foo", repo))

    src_dir = repo / "pipeline" / "foo"
    _write(
        src_dir / ".sealed-provenance.json",
        json.dumps({
            "component_id": "comp-foo",
            "owners": ["team-a"],
            "source_hash": "sha256:" + "0" * 64,
            "verdict": "pass",
        }),
    )
    src = src_dir / "foo.py"
    py_compile.compile(str(src), cfile=importlib.util.cache_from_source(str(src)))
    _write(src_dir / "__pycache__" / "notes.txt", "stale cache\n")
    assert (src_dir / "__pycache__").is_dir()

    after = summary(verifier_orchestrator.verify("comp-foo", repo))

    assert after == before
    assert before[0]["AC-FOO-001"][0] == "pass"
    assert before[0]["AC-FOO-002"][0] == "fail"
    assert before[1] is False
    assert before[3] == "fail"


def test_missing_source_path_fails_overall(tmp_path):
    repo = build(tmp_path / "repo", PASSING_001 + FIXED_002)
    shutil.rmtree(repo / "pipeline" / "foo")
    assert not (repo / "pipeline" / "foo").exists()

    report = verifier_orchestrator.verify("comp-foo", repo)

    assert field(report, "overall") == "fail"