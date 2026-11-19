# hotdocs-criterion: sha256:341656d6636d8da9ebf6b6dac068ffaa61a8f3e6ffb9ada234e76de28f00fabb
import shutil
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = "# Glossary\n\n- **Foo** \u2014 a test term.\n"

PRODUCT = (
    "---\n"
    "id: P-FOO\n"
    "title: Foo Capability\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Foo Capability\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Doubling numbers.\n"
)

COMPONENT = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "realizes: [P-FOO]\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)

REQUIREMENT = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** \u2014 `double(x)` MUST return `2 * x`.\n"
)

ACCEPTANCE = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given a n is 2\n"
    "When double is invoked with [n]\n"
    "Then real equals 4\n"
    "```\n"
)

LIBRARY = (
    "# Library\n"
    "\n"
    "```\n"
    "double(x: int) -> int\n"
    "```\n"
)

CONSTRAINTS = "# Constraints\n\nNone.\n"

GOOD_CODE = (
    "def double(x: int) -> int:\n"
    "    return 2 * x\n"
)

BAD_CODE = (
    "def triple(x: int) -> int:\n"
    "    return 3 * x\n"
)


def assembler_source(repo_root):
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-FOO-001',\n"
        "        'criterion_text': " + repr(ACCEPTANCE) + ",\n"
        "        'requirement_text': " + repr(REQUIREMENT) + ",\n"
        "        'interface': " + repr(LIBRARY) + ",\n"
        "        'glossary': " + repr(GLOSSARY) + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )


def live_root():
    return (
        Path(verifier_orchestrator.__file__).resolve().parents[1]
        / "spec-bundle-assembler"
    ).resolve().parents[1]


def copy_compiler(repo_root):
    src = live_root() / "pipeline" / "criterion-compiler"
    assert src.is_dir(), "real criterion-compiler not found at " + str(src)
    dst = repo_root / "pipeline" / "criterion-compiler"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))


def build_fixture(repo_root, code):
    write(repo_root / "specs" / "glossary.md", GLOSSARY)
    write(repo_root / "specs" / "product" / "foo.md", PRODUCT)
    comp = repo_root / "specs" / "components" / "foo"
    write(comp / "component.md", COMPONENT)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT)
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE)
    write(comp / "interface" / "library.md", LIBRARY)
    write(comp / "constraints.md", CONSTRAINTS)
    write(repo_root / "gen" / "foo" / "foo.py", code)
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(repo_root),
    )
    copy_compiler(repo_root)


def criterion_result(report, criterion_id):
    for c in field(report, "criteria"):
        if field(c, "id") == criterion_id:
            return field(c, "result")
    raise AssertionError("criterion " + criterion_id + " missing from report")


def test_verify_does_not_reuse_module_cached_from_other_repo_root(tmp_path):
    good_1 = tmp_path / "good_1"
    bad = tmp_path / "bad"
    good_2 = tmp_path / "good_2"
    build_fixture(good_1, GOOD_CODE)
    build_fixture(bad, BAD_CODE)
    build_fixture(good_2, GOOD_CODE)

    report_good_1 = verifier_orchestrator.verify("comp-foo", good_1)
    assert field(report_good_1, "interface_drift") is False
    assert criterion_result(report_good_1, "AC-FOO-001") == "pass"

    # Same slug, different repo_root, code lacking the declared function:
    # must reflect this repo's code, not the module loaded for good_1.
    report_bad = verifier_orchestrator.verify("comp-foo", bad)
    assert field(report_bad, "interface_drift") is True
    assert criterion_result(report_bad, "AC-FOO-001") == "fail"

    # And back again: a fresh repo_root with correct code must not reuse
    # the module loaded for the bad repo_root.
    report_good_2 = verifier_orchestrator.verify("comp-foo", good_2)
    assert field(report_good_2, "interface_drift") is False
    assert criterion_result(report_good_2, "AC-FOO-001") == "pass"