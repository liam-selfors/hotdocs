# hotdocs-criterion: sha256:3685e82736058e2c4b76b799d9870eee94675ccba1f61b1760d9d191d48178d2
# AC-VERIFY-014 (covers R-VERIFY-013): two repo_roots holding a component
# with the same slug but different code, verified one after the other in
# the same process, each get results reflecting their own code.

import shutil
from pathlib import Path

import pytest

import verifier_orchestrator


SLUG = "pair-tool"
COMPONENT_ID = "comp-" + SLUG
MODULE = "pair_tool"
CRITERION_ID = "AC-PAIR-001"
REQUIREMENT_ID = "R-PAIR-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def live_root():
    gen_dir = Path(verifier_orchestrator.__file__).resolve().parents[1]
    return (gen_dir / "spec-bundle-assembler").resolve().parents[1]


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def good_module_source():
    return (
        "import types as _types\n"
        "\n"
        "\n"
        "def compute_pair(x):\n"
        "    return _types.SimpleNamespace(value=x * 2)\n"
        "\n"
        "\n"
        "def helper_name(y):\n"
        "    return y\n"
    )


def bad_module_source():
    # Same slug and module name, different code: compute_pair gives the
    # wrong value and the declared helper_name is missing (interface drift).
    return (
        "import types as _types\n"
        "\n"
        "\n"
        "def compute_pair(x):\n"
        "    return _types.SimpleNamespace(value=x * 3)\n"
    )


def assembler_source():
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(REQUIREMENT_ID) + ",\n"
        "        'criterion_text': 'criterion text',\n"
        "        'requirement_text': 'requirement text',\n"
        "        'interface': 'compute_pair(x) -> object',\n"
        "        'glossary': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n"
    )


def probe_source():
    return (
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 0\n"
        "        self.tests_reached = 0\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': True, 'findings': [], 'tests_run': 0, 'tests_reached': 0}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return _Report()\n"
    )


def build_fixture(repo_root, module_source):
    comp = repo_root / "specs" / "components" / SLUG

    write(
        repo_root / "specs" / "product" / "pair.md",
        "---\n"
        "id: P-PAIR\n"
        "title: Pair capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Pair capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubles numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- Doubling.\n"
        "\n"
        "### CS-PAIR-001\n"
        "\n"
        "Covers: P-PAIR\n"
        "\n"
        "```gherkin\n"
        "Given a seed is 2\n"
        "When compute_pair is invoked with [seed]\n"
        "Then value equals 4\n"
        "```\n",
    )

    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Pair tool\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-PAIR]\n"
        "---\n"
        "\n"
        "# Pair tool\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Computes a doubled value.\n"
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
        "- Initial.\n",
    )

    write(
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "# " + REQUIREMENT_ID + "\n"
        "\n"
        "**" + REQUIREMENT_ID + "** - `compute_pair(x)` MUST return an object "
        "whose `value` is `x * 2`.\n",
    )

    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "compute_pair(x) -> object\n"
        "helper_name(y) -> object\n"
        "```\n"
        "\n"
        "`compute_pair` returns an object with attribute `value`, `x * 2`.\n"
        "`helper_name` returns `y`.\n",
    )

    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given a seed is 2\n"
        "When compute_pair is invoked with [seed]\n"
        "Then value equals 4\n"
        "```\n",
    )

    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    write(repo_root / "gen" / SLUG / (MODULE + ".py"), module_source)

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source())

    src = live_root() / "pipeline" / "criterion-compiler"
    dst = repo_root / "pipeline" / "criterion-compiler"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))


def criterion_result(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, criteria
    return field(matches[0], "result")


@pytest.mark.parametrize("order", ["good_first", "bad_first"])
def test_same_slug_in_two_repo_roots_never_shares_a_module(tmp_path, order):
    good_root = tmp_path / "good"
    bad_root = tmp_path / "bad"
    good_root.mkdir()
    bad_root.mkdir()
    build_fixture(good_root, good_module_source())
    build_fixture(bad_root, bad_module_source())

    if order == "good_first":
        sequence = [("good", good_root), ("bad", bad_root)]
    else:
        sequence = [("bad", bad_root), ("good", good_root)]

    reports = {}
    for name, root in sequence:
        reports[name] = verifier_orchestrator.verify(COMPONENT_ID, root)

    good = reports["good"]
    bad = reports["bad"]

    assert field(good, "interface_drift") is False
    assert criterion_result(good) == "pass"

    assert field(bad, "interface_drift") is True
    assert criterion_result(bad) == "fail"
    assert field(bad, "overall") == "fail"