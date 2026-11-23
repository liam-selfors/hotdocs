# hotdocs-criterion: sha256:3f125369b89b3cae89d93d2bcb51c1bd18430f7cebe0b22422f1561e3f9c0769
import shutil
from pathlib import Path

import verifier_orchestrator


SLUG = "drift-fix"
MODULE = "drift_fix"
COMPONENT_ID = "comp-drift-fix"
CRITERION_ID = "AC-DRIFT-001"
REQUIREMENT_ID = "R-DRIFT-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def plant_assembler(repo_root):
    source = (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(REQUIREMENT_ID) + ",\n"
        "        'criterion_text': 'Given x When y Then z',\n"
        "        'requirement_text': 'compute_total MUST add tax.',\n"
        "        'interface': 'compute_total(items: list, tax: float) -> float',\n"
        "        'glossary': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'spec_bundle_hash': 'sha256:' + '0' * 64,\n"
        "        'spec': '',\n"
        "        'interface': 'compute_total(items: list, tax: float) -> float',\n"
        "        'constraints': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'dependency_context': {},\n"
        "        'dependency_usage': {},\n"
        "        'vars': {},\n"
        "        'glossary': '',\n"
        "        'hint_code': None,\n"
        "    }\n"
    )
    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", source)


def plant_probe(repo_root):
    source = (
        "GATE_VERSION = 'test-probe@1.4.0'\n"
        "\n"
        "\n"
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    return _Report()\n"
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", source)


def plant_compiler(repo_root):
    live = (
        Path(verifier_orchestrator.__file__).resolve().parents[1]
        / "spec-bundle-assembler"
    ).resolve().parents[1]
    src = live / "pipeline" / "criterion-compiler"
    dst = repo_root / "pipeline" / "criterion-compiler"
    if src.is_dir():
        shutil.copytree(
            src, dst, ignore=shutil.ignore_patterns("__pycache__")
        )


def build_fixture(repo_root, module_source):
    repo_root = Path(repo_root)
    write(
        repo_root / "specs" / "product" / "fix.md",
        "---\n"
        "id: P-FIX\n"
        "title: Fixture capability\n"
        "status: draft\n"
        "owners: [tests]\n"
        "---\n"
        "\n"
        "# Fixture capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A capability for a fixture.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Drift fixture\n"
        "status: draft\n"
        "owners: [tests]\n"
        "realizes: [P-FIX]\n"
        "---\n"
        "\n"
        "# Drift fixture\n"
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
        "- Initial.\n",
    )
    write(
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "# " + REQUIREMENT_ID + "\n"
        "\n"
        "**" + REQUIREMENT_ID + "** — `compute_total` MUST return the sum of\n"
        "`items` plus `tax`.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "compute_total(items: list, tax: float) -> float\n"
        "```\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given a list of items\n"
        "When compute_total is invoked\n"
        "Then the documentation reads clearly\n"
        "```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "gen" / SLUG / (MODULE + ".py"), module_source)
    plant_assembler(repo_root)
    plant_probe(repo_root)
    plant_compiler(repo_root)
    return repo_root


def make_judge(log_path):
    def judge(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("judge\n")
        return {"result": "pass", "rationale": "fine"}

    return judge


def make_author(log_path):
    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("author\n")
        return {
            "model": "fake",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": {"category": "model", "message": "not expected"},
            "file": None,
        }

    return test_author


def run_verify(tmp_path, module_source):
    repo_root = build_fixture(tmp_path / "repo", module_source)
    log = tmp_path / "calls.log"
    return verifier_orchestrator.verify(
        COMPONENT_ID,
        repo_root,
        judge=make_judge(log),
        test_author=make_author(log),
    )


def test_missing_documented_callable_is_drift_and_fails(tmp_path):
    source = (
        "def other_function(items, tax):\n"
        "    return sum(items) + tax\n"
    )
    report = run_verify(tmp_path, source)
    assert field(report, "interface_drift") is True
    assert field(report, "overall") == "fail"


def test_parameter_mismatch_is_drift_and_fails(tmp_path):
    source = (
        "def compute_total(items, rate):\n"
        "    return sum(items) + rate\n"
    )
    report = run_verify(tmp_path, source)
    assert field(report, "interface_drift") is True
    assert field(report, "overall") == "fail"


def test_matching_interface_is_not_drift(tmp_path):
    source = (
        "def compute_total(items, tax):\n"
        "    return sum(items) + tax\n"
        "\n"
        "\n"
        "def undocumented_helper(a, b, c):\n"
        "    return a\n"
    )
    report = run_verify(tmp_path, source)
    assert field(report, "interface_drift") is False