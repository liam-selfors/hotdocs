# hotdocs-criterion: sha256:1e1dcc1f10f271b05b84837170316f16214b51f36e935d940f7e76f748104493
"""AC-VERIFY-014 / R-VERIFY-013.

Two repo_roots each hold a component with the same slug (`widget`) but
different code. `verify` runs against each in turn in one process; each
report's `interface_drift` and compiled-criterion result must reflect its
own repo_root's code, never a module cached from the other repo_root.
"""

import shutil
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
MODULE = "widget"
CRITERION_ID = "AC-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def live_root():
    return (
        Path(verifier_orchestrator.__file__).resolve().parents[1]
        / "spec-bundle-assembler"
    ).resolve().parents[1]


COMPONENT_MD = (
    "---\n"
    "id: comp-widget\n"
    "title: Widget\n"
    "status: draft\n"
    "owners: [test-team]\n"
    "depends_on: []\n"
    "realizes: [P-WIDGET]\n"
    "---\n"
    "\n"
    "# Widget\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Computes a widget value.\n"
)

CAPABILITY_MD = (
    "---\n"
    "id: P-WIDGET\n"
    "title: Widget capability\n"
    "status: draft\n"
    "owners: [test-team]\n"
    "---\n"
    "\n"
    "# Widget capability\n"
    "\n"
    "Widgets can be computed.\n"
)

REQUIREMENT_MD = (
    "# R-WIDGET-001\n"
    "\n"
    "**R-WIDGET-001** - `compute(x)` MUST return an object whose `value`\n"
    "is twice `x`; `describe(x)` MUST return a description of `x`.\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "compute(x)\n"
    "describe(x)\n"
    "```\n"
    "\n"
    "`compute` returns an object with attribute `value`.\n"
)

ACCEPTANCE_MD = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given a n is 2\n"
    "When compute is invoked with [2]\n"
    "Then value equals 4\n"
    "```\n"
)

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

GLOSSARY_MD = "# Glossary\n\nNo terms.\n"

TEST_PROBE_SRC = (
    "class _Report:\n"
    "    def __init__(self):\n"
    "        self.ok = True\n"
    "        self.findings = []\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'ok': self.ok, 'findings': list(self.findings)}\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
    "    return _Report()\n"
)

# Repo A: matches the interface (both functions) and passes the criterion.
CODE_A = (
    "import types\n"
    "\n"
    "\n"
    "def compute(x):\n"
    "    return types.SimpleNamespace(value=x * 2)\n"
    "\n"
    "\n"
    "def describe(x):\n"
    "    return 'widget ' + str(x)\n"
)

# Repo B: same slug and module name, but lacks `describe` (interface drift)
# and computes the wrong value (criterion fails).
CODE_B = (
    "import types\n"
    "\n"
    "\n"
    "def compute(x):\n"
    "    return types.SimpleNamespace(value=x * 3)\n"
)


def build_fixture(repo_root, module_source):
    comp = repo_root / "specs" / "components" / SLUG
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "constraints.md", CONSTRAINTS_MD)
    write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT_MD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "acceptance" / (CRITERION_ID + ".md"), ACCEPTANCE_MD)
    write(repo_root / "specs" / "product" / "widget.md", CAPABILITY_MD)
    write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)

    write(repo_root / "gen" / SLUG / (MODULE + ".py"), module_source)
    write(repo_root / "gen" / "test-probe" / "test_probe.py", TEST_PROBE_SRC)

    src = live_root() / "pipeline" / "criterion-compiler"
    dst = repo_root / "pipeline" / "criterion-compiler"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"),
    )
    return repo_root


def criterion_result(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, criteria
    c = matches[0]
    assert field(c, "kind") == "compiled", c
    return field(c, "result")


def assert_report_a(report):
    assert field(report, "component_id") == COMPONENT_ID
    assert field(report, "interface_drift") is False, (
        "repo A's code matches its interface, so interface_drift must be False"
    )
    assert criterion_result(report) == "pass", (
        "repo A's compute(2).value is 4, so its compiled criterion must pass"
    )


def assert_report_b(report):
    assert field(report, "component_id") == COMPONENT_ID
    assert field(report, "interface_drift") is True, (
        "repo B's code lacks describe, so interface_drift must be True"
    )
    assert criterion_result(report) == "fail", (
        "repo B's compute(2).value is 6, so its compiled criterion must fail"
    )


def test_same_slug_in_two_repo_roots_never_shares_modules(tmp_path):
    repo_a = build_fixture(tmp_path / "repo_a", CODE_A)
    repo_b = build_fixture(tmp_path / "repo_b", CODE_B)

    report_a = verifier_orchestrator.verify(COMPONENT_ID, repo_a)
    assert_report_a(report_a)

    report_b = verifier_orchestrator.verify(COMPONENT_ID, repo_b)
    assert_report_b(report_b)

    # And back again: repo A must not now see repo B's module.
    report_a_again = verifier_orchestrator.verify(COMPONENT_ID, repo_a)
    assert_report_a(report_a_again)