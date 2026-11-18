# hotdocs-criterion: sha256:f00d560fd75d6b9f9615075acc008c6eaa97d563a7883f0562af40c5a166c7f4
import shutil
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def optional_field(value, name):
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def write(path, text):
    path = Path(path)
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
    "Foo doubles a number.\n"
)

LIBRARY_MD = "# Library\n\n```\ndo_the_thing(x)\n```\n"

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

FOO_SOURCE = "def do_the_thing(x):\n    return 2 * x\n"

ASSEMBLER_SOURCE = (
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    covers = 'R-' + criterion_id[len('AC-'):]\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': covers,\n"
    "        'criterion_text': 'criterion text for ' + criterion_id,\n"
    "        'requirement_text': 'requirement text for ' + covers,\n"
    "        'interface': " + repr(LIBRARY_MD) + ",\n"
    "        'glossary': " + repr(GLOSSARY) + ",\n"
    "        'dependency_interfaces': {},\n"
    "    }\n"
)


def requirement_text(num):
    rid = "R-FOO-" + num
    return "# " + rid + "\n\n**" + rid + "** — `do_the_thing(x)` MUST return `2 * x`.\n"


def acceptance_text(num):
    return (
        "# AC-FOO-" + num + "\n"
        "\n"
        "Covers: R-FOO-" + num + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x is 2\n"
        "When do_the_thing is invoked with 2\n"
        "Then it returns 4\n"
        "```\n"
    )


def characterization_source(fixed, extra_0031=False):
    src = (
        "def test_ac_foo_001_returns_value():\n"
        "    assert 1 + 1 == 2\n"
        "\n"
        "\n"
        "def test_ac_foo_001_other():\n"
        "    assert True\n"
        "\n"
        "\n"
        "def test_ac_foo_002_fails():\n"
        "    assert " + ("True" if fixed else "False") + "\n"
    )
    if extra_0031:
        src += (
            "\n"
            "\n"
            "def test_ac_foo_0031_x():\n"
            "    assert True\n"
        )
    return src


def build_fixture(repo_root, nums=("001", "002"), fixed=False, extra_0031=False):
    repo_root = Path(repo_root)
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "constraints.md", CONSTRAINTS_MD)
    for num in nums:
        write(comp / "requirements" / ("R-FOO-" + num + ".md"), requirement_text(num))
        write(comp / "acceptance" / ("AC-FOO-" + num + ".md"), acceptance_text(num))
    write(repo_root / "pipeline" / "foo" / "foo.py", FOO_SOURCE)
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        ASSEMBLER_SOURCE,
    )
    write(
        repo_root / "verification" / "foo" / "test_foo.py",
        characterization_source(fixed, extra_0031),
    )
    return repo_root


def criteria_by_id(report):
    return {field(c, "id"): c for c in field(report, "criteria")}


def snapshot(report):
    crit = {}
    for cid, c in criteria_by_id(report).items():
        detail = optional_field(c, "failure_detail")
        crit[cid] = (field(c, "result"), optional_field(detail, "message"))
    return {
        "criteria": crit,
        "interface_drift": field(report, "interface_drift"),
        "mutation_score": field(report, "mutation_score"),
        "overall": field(report, "overall"),
    }


def test_sealed_component_initial_verdicts(tmp_path):
    repo_root = build_fixture(tmp_path / "repo")
    report = verifier_orchestrator.verify("comp-foo", repo_root)

    crit = criteria_by_id(report)
    assert field(crit["AC-FOO-001"], "result") == "pass"
    assert field(crit["AC-FOO-002"], "result") == "fail"
    assert optional_field(crit["AC-FOO-002"], "failure_detail")
    assert field(report, "interface_drift") is False
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"


def test_sealed_component_fixed_test_passes_overall(tmp_path):
    repo_root = build_fixture(tmp_path / "repo")
    first = verifier_orchestrator.verify("comp-foo", repo_root)
    assert field(first, "overall") == "fail"

    write(
        repo_root / "verification" / "foo" / "test_foo.py",
        characterization_source(fixed=True),
    )
    report = verifier_orchestrator.verify("comp-foo", repo_root)
    crit = criteria_by_id(report)
    assert field(crit["AC-FOO-001"], "result") == "pass"
    assert field(crit["AC-FOO-002"], "result") == "pass"
    assert field(report, "interface_drift") is False
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "pass"


def test_sealed_component_criterion_without_matching_test(tmp_path):
    repo_root = build_fixture(
        tmp_path / "repo", nums=("001", "002", "003"), fixed=True, extra_0031=True
    )
    report = verifier_orchestrator.verify("comp-foo", repo_root)
    crit = criteria_by_id(report)
    assert field(crit["AC-FOO-001"], "result") == "pass"
    assert field(crit["AC-FOO-002"], "result") == "pass"
    assert field(crit["AC-FOO-003"], "result") == "fail"
    detail = optional_field(crit["AC-FOO-003"], "failure_detail")
    assert detail is not None
    assert field(detail, "message") == "no characterization test"
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"


def test_sealed_component_ignores_provenance_and_pycache(tmp_path):
    repo_root = build_fixture(tmp_path / "repo", fixed=True)
    before = verifier_orchestrator.verify("comp-foo", repo_root)
    before_snap = snapshot(before)
    assert before_snap["overall"] == "pass"

    src = repo_root / "pipeline" / "foo"
    write(
        src / ".sealed-provenance.json",
        '{"owners": ["team-a"], "source_hash": "sha256:' + "0" * 64 + '"}\n',
    )
    pycache = src / "__pycache__"
    pycache.mkdir(parents=True, exist_ok=True)
    (pycache / "foo.cpython-311.pyc").write_bytes(b"\x00\x01junk-bytes\xff")
    write(pycache / "stray.py", "def stray_public_function(a, b):\n    return a\n")

    after = verifier_orchestrator.verify("comp-foo", repo_root)
    assert snapshot(after) == before_snap


def test_sealed_component_missing_source_path_fails_overall(tmp_path):
    repo_root = build_fixture(tmp_path / "repo", fixed=True)
    first = verifier_orchestrator.verify("comp-foo", repo_root)
    assert field(first, "overall") == "pass"

    shutil.rmtree(repo_root / "pipeline" / "foo")
    report = verifier_orchestrator.verify("comp-foo", repo_root)
    assert field(report, "overall") == "fail"