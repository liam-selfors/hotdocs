# hotdocs-criterion: sha256:d53416de699f4c79db0db8f3c7b972b8e2ef06cad58a361e6b6135e1a273000a
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


ASSEMBLER_SOURCE = (
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': 'R-FOO-001',\n"
    "        'criterion_text': 'criterion text',\n"
    "        'requirement_text': 'requirement text',\n"
    "        'interface': 'compute_total(a: int, b: int) -> int',\n"
    "        'glossary': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'testing': '',\n"
    "    }\n"
)

PROBE_SOURCE = (
    "class ProbeReport:\n"
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
    "    return ProbeReport()\n"
)

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team]\n"
    "realizes: [P-FOO]\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Computes totals.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: totals.\n"
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

PRODUCT_MD = (
    "---\n"
    "id: P-FOO\n"
    "title: Foo capability\n"
    "status: draft\n"
    "owners: [team]\n"
    "---\n"
    "\n"
    "# Foo capability\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Totals.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- Totals.\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "compute_total(a: int, b: int) -> int\n"
    "```\n"
    "\n"
    "`compute_total` returns the sum of `a` and `b`.\n"
)

REQUIREMENT_MD = (
    "# R-FOO-001\n"
    "\n"
    "**R-FOO-001** — `compute_total` MUST return the sum of its arguments.\n"
)

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: llm-judge\n"
    "\n"
    "```gherkin\n"
    "Given the component's interface\n"
    "When it is read\n"
    "Then it is clear\n"
    "```\n"
)


def build_fixture(root, module_source):
    root = Path(root)
    comp = root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "component.md").write_text(COMPONENT_MD)
    (comp / "requirements" / "R-FOO-001.md").write_text(REQUIREMENT_MD)
    (comp / "interface" / "library.md").write_text(LIBRARY_MD)
    (comp / "acceptance" / "AC-FOO-001.md").write_text(ACCEPTANCE_MD)
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n")
    (root / "specs" / "product").mkdir(parents=True)
    (root / "specs" / "product" / "foo.md").write_text(PRODUCT_MD)
    (root / "specs" / "glossary.md").write_text("# Glossary\n")

    gen = root / "gen"
    (gen / "foo").mkdir(parents=True)
    (gen / "foo" / "foo.py").write_text(module_source)
    (gen / "spec-bundle-assembler").mkdir(parents=True)
    (gen / "spec-bundle-assembler" / "spec_bundle_assembler.py").write_text(ASSEMBLER_SOURCE)
    (gen / "test-probe").mkdir(parents=True)
    (gen / "test-probe" / "test_probe.py").write_text(PROBE_SOURCE)
    return root


def make_judge(log_path):
    def judge(bundle):
        with open(log_path, "a") as fh:
            fh.write("called\n")
        return {"result": "pass", "rationale": "clear"}

    return judge


def run_verify(tmp_path, module_source):
    repo_root = build_fixture(tmp_path / "repo", module_source)
    log_path = tmp_path / "judge.log"
    report = verifier_orchestrator.verify(
        "comp-foo", repo_root, judge=make_judge(log_path), test_author=None
    )
    return report


def test_parameter_mismatch_is_drift_and_fails(tmp_path):
    source = (
        "def compute_total(a):\n"
        "    return a\n"
    )
    report = run_verify(tmp_path, source)
    assert field(report, "interface_drift") is True
    assert field(report, "overall") == "fail"
    as_dict = report.to_dict()
    assert as_dict["interface_drift"] is True
    assert as_dict["overall"] == "fail"
    json.dumps(as_dict)


def test_missing_callable_is_drift_and_fails(tmp_path):
    source = (
        "def other_name(a, b):\n"
        "    return a + b\n"
    )
    report = run_verify(tmp_path, source)
    assert field(report, "interface_drift") is True
    assert field(report, "overall") == "fail"


def test_matching_interface_is_not_drift(tmp_path):
    source = (
        "def compute_total(a, b):\n"
        "    return a + b\n"
        "\n"
        "\n"
        "def helper_extra(x):\n"
        "    return x\n"
    )
    report = run_verify(tmp_path, source)
    assert field(report, "interface_drift") is False