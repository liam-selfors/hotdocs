# hotdocs-criterion: sha256:034905ede6080aad148672f6e18f6892429ee818aea63dd509400af8dbc19954
import shutil
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def opt_field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "sealed: true\n"
    "source_path: pipeline/foo/\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Does the thing.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: doing the thing.\n"
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
    "- Initial.\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "do_the_thing(x) -> int\n"
    "```\n"
    "\n"
    "`do_the_thing` returns `x` plus one.\n"
)

FOO_PY = (
    "def do_the_thing(x):\n"
    "    return x + 1\n"
)

ASSEMBLER_PY = (
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': 'R-' + criterion_id[3:],\n"
    "        'criterion_text': 'criterion text',\n"
    "        'requirement_text': 'requirement text',\n"
    "        'interface': 'do_the_thing(x) -> int',\n"
    "        'glossary': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'testing': '',\n"
    "    }\n"
    "\n"
    "\n"
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    raise RuntimeError('assemble is not expected to be called')\n"
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

TEST_001 = (
    "def test_ac_foo_001_returns_value():\n"
    "    assert 1 + 1 == 2\n"
    "\n"
    "\n"
    "def test_ac_foo_001_other():\n"
    "    assert 'a' == 'a'\n"
)

TEST_002_FAILING = (
    "\n"
    "\n"
    "def test_ac_foo_002_fails():\n"
    "    assert 1 == 2\n"
)

TEST_002_PASSING = (
    "\n"
    "\n"
    "def test_ac_foo_002_fails():\n"
    "    assert 2 == 2\n"
)

TEST_0031 = (
    "\n"
    "\n"
    "def test_ac_foo_0031_x():\n"
    "    assert True\n"
)


def requirement_text(num):
    return (
        "# R-FOO-" + num + "\n"
        "\n"
        "**R-FOO-" + num + "** - `do_the_thing(x)` MUST return `x` plus one.\n"
    )


def acceptance_text(num):
    return (
        "# AC-FOO-" + num + "\n"
        "\n"
        "Covers: R-FOO-" + num + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given an input of 1\n"
        "When do_the_thing is called with it\n"
        "Then it returns 2\n"
        "```\n"
    )


def build_fixture(repo_root, test_file_source, criteria=("001", "002")):
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    for num in criteria:
        write(comp / "requirements" / ("R-FOO-" + num + ".md"), requirement_text(num))
        write(comp / "acceptance" / ("AC-FOO-" + num + ".md"), acceptance_text(num))
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Thing** - a thing.\n")
    write(repo_root / "pipeline" / "foo" / "foo.py", FOO_PY)
    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", ASSEMBLER_PY)
    write(repo_root / "gen" / "test-probe" / "test_probe.py", PROBE_PY)
    write(repo_root / "verification" / "foo" / "test_foo.py", test_file_source)


def criterion(report, cid):
    matches = [c for c in field(report, "criteria") if field(c, "id") == cid]
    assert len(matches) == 1, (cid, field(report, "criteria"))
    return matches[0]


def summarize(report):
    rows = []
    for c in field(report, "criteria"):
        detail = opt_field(c, "failure_detail")
        message = None
        if detail is not None:
            message = field(detail, "message")
        rows.append((field(c, "id"), field(c, "result"), message))
    return (
        sorted(rows),
        field(report, "overall"),
        field(report, "interface_drift"),
        field(report, "mutation_score"),
    )


def test_ac_verify_019_initial_run(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, TEST_001 + TEST_002_FAILING)
    assert not (repo_root / "gen" / "foo").exists()

    report = verifier_orchestrator.verify("comp-foo", repo_root)

    c1 = criterion(report, "AC-FOO-001")
    assert field(c1, "result") == "pass"
    c2 = criterion(report, "AC-FOO-002")
    assert field(c2, "result") == "fail"
    detail = opt_field(c2, "failure_detail")
    assert detail is not None
    assert detail
    assert field(report, "interface_drift") is False
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"


def test_ac_verify_019_fixed_test_passes(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, TEST_001 + TEST_002_FAILING)
    first = verifier_orchestrator.verify("comp-foo", repo_root)
    assert field(first, "overall") == "fail"

    write(repo_root / "verification" / "foo" / "test_foo.py", TEST_001 + TEST_002_PASSING)
    report = verifier_orchestrator.verify("comp-foo", repo_root)

    assert field(criterion(report, "AC-FOO-001"), "result") == "pass"
    assert field(criterion(report, "AC-FOO-002"), "result") == "pass"
    assert field(report, "interface_drift") is False
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "pass"


def test_ac_verify_019_missing_characterization_test(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(
        repo_root,
        TEST_001 + TEST_002_PASSING + TEST_0031,
        criteria=("001", "002", "003"),
    )

    report = verifier_orchestrator.verify("comp-foo", repo_root)

    assert field(criterion(report, "AC-FOO-001"), "result") == "pass"
    assert field(criterion(report, "AC-FOO-002"), "result") == "pass"
    c3 = criterion(report, "AC-FOO-003")
    assert field(c3, "result") == "fail"
    detail = opt_field(c3, "failure_detail")
    assert detail is not None
    assert field(detail, "message") == "no characterization test"
    assert field(report, "overall") == "fail"


def test_ac_verify_019_provenance_and_pycache_ignored(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(
        repo_root,
        TEST_001 + TEST_002_PASSING + TEST_0031,
        criteria=("001", "002", "003"),
    )
    before = summarize(verifier_orchestrator.verify("comp-foo", repo_root))

    source = repo_root / "pipeline" / "foo"
    write(
        source / ".sealed-provenance.json",
        '{"owners": ["pipeline-team"], "source_sha256": "sha256:' + "0" * 64 + '"}\n',
    )
    pycache = source / "__pycache__"
    pycache.mkdir(parents=True, exist_ok=True)
    (pycache / "foo.cpython-312.pyc").write_bytes(b"not really bytecode")

    after = summarize(verifier_orchestrator.verify("comp-foo", repo_root))
    assert after == before


def test_ac_verify_019_missing_source_dir_fails(tmp_path):
    repo_root = tmp_path / "repo"
    build_fixture(repo_root, TEST_001 + TEST_002_PASSING)
    ok = verifier_orchestrator.verify("comp-foo", repo_root)
    assert field(ok, "overall") == "pass"

    shutil.rmtree(repo_root / "pipeline" / "foo")
    assert not (repo_root / "pipeline" / "foo").exists()

    report = verifier_orchestrator.verify("comp-foo", repo_root)
    assert field(report, "overall") == "fail"