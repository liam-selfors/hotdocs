# hotdocs-criterion: sha256:6cf3ba00fcf1ff22e6b29781e419a6978feef80afd34394eb551c44edde2c6f8
import json
import shutil
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


ASSEMBLER_SOURCE = (
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': 'R-' + criterion_id[3:],\n"
    "        'criterion_text': 'text',\n"
    "        'requirement_text': 'req',\n"
    "        'interface': 'do_the_thing(x) -> int',\n"
    "        'glossary': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'testing': '',\n"
    "    }\n"
)

PROBE_SOURCE = (
    "class _Report:\n"
    "    def __init__(self):\n"
    "        self.ok = True\n"
    "        self.findings = []\n"
    "        self.tests_run = 1\n"
    "        self.tests_reached = 1\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'ok': self.ok, 'findings': list(self.findings),\n"
    "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
    "    return _Report()\n"
)

CODE_SOURCE = (
    "def do_the_thing(x):\n"
    "    return x + 1\n"
)

CHAR_PASSING_002 = (
    "def test_ac_foo_002_fails():\n"
    "    assert 2 + 2 == 4\n"
)

CHAR_FAILING_002 = (
    "def test_ac_foo_002_fails():\n"
    "    assert 2 + 2 == 5\n"
)

CHAR_COMMON = (
    "def test_ac_foo_001_returns_value():\n"
    "    assert 1 + 1 == 2\n"
    "\n"
    "\n"
    "def test_ac_foo_001_other():\n"
    "    assert 'a' == 'a'\n"
    "\n"
    "\n"
)

CHAR_0031 = (
    "\n"
    "\n"
    "def test_ac_foo_0031_x():\n"
    "    assert True\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def add_criterion(comp, num):
    rid = "R-FOO-" + num
    aid = "AC-FOO-" + num
    write(
        comp / "requirements" / (rid + ".md"),
        "**" + rid + "** — `do_the_thing` MUST return a value (" + num + ").\n",
    )
    write(
        comp / "acceptance" / (aid + ".md"),
        "# " + aid + "\n\n"
        "Covers: " + rid + "\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a value is 1\n"
        "When do_the_thing is invoked with 1\n"
        "Then result equals 2\n"
        "```\n",
    )


def build_fixture(repo_root, failing=True, third=False):
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: pipeline/foo/\n"
        "---\n\n"
        "# Foo\n\n"
        "## Purpose\n\nDoes the thing.\n\n"
        "## Scope\n\n- In scope: the thing.\n\n"
        "## Definitions\n\nNone.\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n"
        "## Change log\n\n- Initial.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n"
        "```\n"
        "do_the_thing(x) -> int\n"
        "```\n\n"
        "Returns `x + 1`.\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    add_criterion(comp, "001")
    add_criterion(comp, "002")
    if third:
        add_criterion(comp, "003")
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Thing** — a thing.\n")
    write(repo_root / "pipeline" / "foo" / "foo.py", CODE_SOURCE)
    char = CHAR_COMMON + (CHAR_FAILING_002 if failing else CHAR_PASSING_002)
    if third:
        char = char + CHAR_0031
    write(repo_root / "verification" / "foo" / "test_foo.py", char)
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        ASSEMBLER_SOURCE,
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", PROBE_SOURCE)


def run_verify(repo_root):
    return verifier_orchestrator.verify("comp-foo", repo_root)


def criterion(report, cid):
    matches = [c for c in field(report, "criteria") if field(c, "id") == cid]
    assert len(matches) == 1, cid
    return matches[0]


def summary(report):
    out = {}
    for c in field(report, "criteria"):
        out[field(c, "id")] = field(c, "result")
    return (
        out,
        field(report, "interface_drift"),
        field(report, "mutation_score"),
        field(report, "overall"),
    )


def test_ac_verify_019_failing_criterion(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, failing=True)
    assert not (repo_root / "gen" / "foo").exists()
    report = run_verify(repo_root)
    assert field(criterion(report, "AC-FOO-001"), "result") == "pass"
    c2 = criterion(report, "AC-FOO-002")
    assert field(c2, "result") == "fail"
    fd = c2.get("failure_detail") if isinstance(c2, dict) else getattr(c2, "failure_detail", None)
    assert fd
    assert field(report, "interface_drift") is False
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"


def test_ac_verify_019_fixed_passes(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, failing=False)
    report = run_verify(repo_root)
    assert field(criterion(report, "AC-FOO-001"), "result") == "pass"
    assert field(criterion(report, "AC-FOO-002"), "result") == "pass"
    assert field(report, "interface_drift") is False
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "pass"


def test_ac_verify_019_no_characterization_test(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, failing=False, third=True)
    report = run_verify(repo_root)
    assert field(criterion(report, "AC-FOO-001"), "result") == "pass"
    assert field(criterion(report, "AC-FOO-002"), "result") == "pass"
    c3 = criterion(report, "AC-FOO-003")
    assert field(c3, "result") == "fail"
    assert field(field(c3, "failure_detail"), "message") == "no characterization test"
    assert field(report, "overall") == "fail"


def test_ac_verify_019_provenance_and_pycache_ignored(tmp_path):
    for failing in (False, True):
        repo_root = tmp_path / ("repo_" + str(failing))
        build_fixture(repo_root, failing=failing)
        before = summary(run_verify(repo_root))
        src = repo_root / "pipeline" / "foo"
        write(
            src / ".sealed-provenance.json",
            json.dumps({"owners": ["team-a"], "source_sha256": "sha256:" + "0" * 64}),
        )
        cache = src / "__pycache__"
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "foo.cpython-312.pyc").write_bytes(b"\x00\x01garbage\xff")
        write(cache / "extra.py", "def undocumented_name():\n    return 0\n")
        after = summary(run_verify(repo_root))
        assert after == before


def test_ac_verify_019_missing_source_dir(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, failing=False)
    shutil.rmtree(repo_root / "pipeline" / "foo")
    report = run_verify(repo_root)
    assert field(report, "overall") == "fail"