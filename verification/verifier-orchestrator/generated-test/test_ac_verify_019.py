# hotdocs-criterion: sha256:f00d560fd75d6b9f9615075acc008c6eaa97d563a7883f0562af40c5a166c7f4
import shutil
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: doubling.\n"
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
    "do_the_thing(x: int) -> int\n"
    "```\n"
    "\n"
    "`do_the_thing` returns `2 * x`.\n"
)

FOO_PY = (
    "def do_the_thing(x: int) -> int:\n"
    "    \"\"\"Return twice x.\"\"\"\n"
    "    return 2 * x\n"
)

FAKE_ASSEMBLER = (
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': 'R-' + criterion_id[3:],\n"
    "        'criterion_text': 'criterion',\n"
    "        'requirement_text': 'requirement',\n"
    "        'interface': 'interface',\n"
    "        'glossary': 'glossary',\n"
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
        "When do_the_thing is invoked with [2]\n"
        "Then result equals 4\n"
        "```\n"
    )


def characterization_source(second_passes, extra_0031=False):
    src = (
        "def test_ac_foo_001_returns_value():\n"
        "    assert 2 * 2 == 4\n"
        "\n"
        "\n"
        "def test_ac_foo_001_other():\n"
        "    assert 3 * 2 == 6\n"
        "\n"
        "\n"
        "def test_ac_foo_002_fails():\n"
    )
    if second_passes:
        src += "    assert 1 + 1 == 2\n"
    else:
        src += "    assert 1 + 1 == 3\n"
    if extra_0031:
        src += (
            "\n"
            "\n"
            "def test_ac_foo_0031_x():\n"
            "    assert True\n"
        )
    return src


def build_fixture(repo_root):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT_MD)
    for num in ("001", "002"):
        write(comp / "requirements" / ("R-FOO-" + num + ".md"), requirement_text(num))
        write(comp / "acceptance" / ("AC-FOO-" + num + ".md"), acceptance_text(num))
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "pipeline" / "foo" / "foo.py", FOO_PY)
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        FAKE_ASSEMBLER,
    )
    write(
        repo_root / "verification" / "foo" / "test_foo.py",
        characterization_source(second_passes=False),
    )


def criteria_by_id(report):
    return {field(c, "id"): c for c in field(report, "criteria")}


def summary(report):
    out = []
    for c in field(report, "criteria"):
        detail = c.get("failure_detail") if isinstance(c, dict) else getattr(c, "failure_detail", None)
        message = None
        if detail is not None:
            message = field(detail, "message")
        out.append((field(c, "id"), field(c, "result"), message))
    return (
        sorted(out),
        field(report, "interface_drift"),
        field(report, "mutation_score"),
        field(report, "overall"),
    )


def test_sealed_component_verified_by_characterization_tests(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    comp = repo_root / "specs" / "components" / "foo"

    # Scenario 1: one criterion passes, one fails.
    report = verifier_orchestrator.verify("comp-foo", repo_root)
    crit = criteria_by_id(report)
    assert field(crit["AC-FOO-001"], "result") == "pass"
    assert field(crit["AC-FOO-002"], "result") == "fail"
    c2 = crit["AC-FOO-002"]
    detail = c2.get("failure_detail") if isinstance(c2, dict) else getattr(c2, "failure_detail", None)
    assert detail
    assert field(report, "interface_drift") is False
    assert field(report, "mutation_score") is None
    assert field(report, "overall") == "fail"

    # Scenario 2: AC-FOO-002's test fixed.
    write(
        repo_root / "verification" / "foo" / "test_foo.py",
        characterization_source(second_passes=True),
    )
    report = verifier_orchestrator.verify("comp-foo", repo_root)
    crit = criteria_by_id(report)
    assert field(crit["AC-FOO-001"], "result") == "pass"
    assert field(crit["AC-FOO-002"], "result") == "pass"
    assert field(report, "overall") == "pass"

    # Scenario 3: AC-FOO-003 with no matching test; test_ac_foo_0031_x doesn't count.
    write(comp / "requirements" / "R-FOO-003.md", requirement_text("003"))
    write(comp / "acceptance" / "AC-FOO-003.md", acceptance_text("003"))
    write(
        repo_root / "verification" / "foo" / "test_foo.py",
        characterization_source(second_passes=True, extra_0031=True),
    )
    report = verifier_orchestrator.verify("comp-foo", repo_root)
    crit = criteria_by_id(report)
    assert field(crit["AC-FOO-001"], "result") == "pass"
    assert field(crit["AC-FOO-002"], "result") == "pass"
    c3 = crit["AC-FOO-003"]
    assert field(c3, "result") == "fail"
    detail3 = c3.get("failure_detail") if isinstance(c3, dict) else getattr(c3, "failure_detail", None)
    assert detail3 is not None
    assert field(detail3, "message") == "no characterization test"
    assert field(report, "overall") == "fail"
    before = summary(report)

    # Scenario 4: provenance manifest and __pycache__ are ignored.
    write(repo_root / "pipeline" / "foo" / ".sealed-provenance.json", "not even json {")
    pycache = repo_root / "pipeline" / "foo" / "__pycache__"
    pycache.mkdir(parents=True, exist_ok=True)
    (pycache / "foo.cpython-311.pyc").write_bytes(b"\x00\x01garbage\xff")
    write(pycache / "extra.py", "def undocumented_helper(y):\n    return y\n")
    report = verifier_orchestrator.verify("comp-foo", repo_root)
    after = summary(report)
    assert after == before

    # Scenario 5: source_path directory removed.
    shutil.rmtree(repo_root / "pipeline" / "foo")
    report = verifier_orchestrator.verify("comp-foo", repo_root)
    assert field(report, "overall") == "fail"