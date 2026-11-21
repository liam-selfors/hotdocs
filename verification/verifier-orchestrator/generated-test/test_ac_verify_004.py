# hotdocs-criterion: sha256:163642fa4c17da224d2f1b6caf1b50f8a439831aefce46eca93927dfda3768b6
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
    "        'covers': 'R-WIDGET-001',\n"
    "        'criterion_text': 'Given a widget When made Then it is made',\n"
    "        'requirement_text': 'R-WIDGET-001 widget_make MUST make a widget.',\n"
    "        'interface': 'widget_make(size: int, color: str) -> dict',\n"
    "        'glossary': '# Glossary',\n"
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
    "\n"
    "\n"
    "GATE_VERSION = 'test-probe@1.3.0'\n"
)

COMPONENT_MD = (
    "---\n"
    "id: comp-widget\n"
    "title: Widget\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "realizes: [P-WIDGET]\n"
    "---\n"
    "\n"
    "# Widget\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Makes widgets.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: making widgets.\n"
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
    "id: P-WIDGET\n"
    "title: Widgets\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "---\n"
    "\n"
    "# Widgets\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Widgets exist.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- Widgets.\n"
    "\n"
    "### CS-WIDGET-001\n"
    "\n"
    "Covers: P-WIDGET\n"
    "\n"
    "```gherkin\n"
    "Given a size is 1\n"
    "When widget_make is invoked with [1, \"red\"]\n"
    "Then size equals 1\n"
    "```\n"
)

LIBRARY_MD = (
    "# Library\n"
    "\n"
    "```\n"
    "widget_make(size: int, color: str) -> dict\n"
    "```\n"
    "\n"
    "`widget_make` returns a dict describing the widget.\n"
)

REQUIREMENT_MD = (
    "# R-WIDGET-001\n"
    "\n"
    "**R-WIDGET-001** — `widget_make` MUST return a dict describing the widget.\n"
)

ACCEPTANCE_MD = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: llm-judge\n"
    "\n"
    "```gherkin\n"
    "Given a widget spec\n"
    "When a reviewer reads it\n"
    "Then it is clear\n"
    "```\n"
)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_live_compiler(repo_root):
    live = (
        Path(verifier_orchestrator.__file__).resolve().parents[1] / "spec-bundle-assembler"
    ).resolve().parents[1]
    src = live / "pipeline" / "criterion-compiler"
    if src.is_dir():
        shutil.copytree(
            src,
            repo_root / "pipeline" / "criterion-compiler",
            ignore=shutil.ignore_patterns("__pycache__"),
        )


def build_fixture(repo_root, module_source):
    comp = repo_root / "specs" / "components" / "widget"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT_MD)
    write(comp / "acceptance" / "AC-WIDGET-001.md", ACCEPTANCE_MD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(repo_root / "specs" / "product" / "widget.md", PRODUCT_MD)
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** — a thing.\n")
    write(repo_root / "gen" / "widget" / "widget.py", module_source)
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        ASSEMBLER_SOURCE,
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", PROBE_SOURCE)
    copy_live_compiler(repo_root)
    return repo_root


def passing_judge(bundle):
    return {"result": "pass", "rationale": "clear enough"}


def run_verify(repo_root):
    return verifier_orchestrator.verify("comp-widget", repo_root, judge=passing_judge)


def test_parameter_mismatch_is_drift_and_fails(tmp_path):
    repo_root = build_fixture(
        tmp_path / "repo",
        "def widget_make(size):\n    return {'size': size}\n",
    )
    report = run_verify(repo_root)
    assert field(report, "interface_drift") is True
    assert field(report, "overall") == "fail"


def test_missing_callable_is_drift_and_fails(tmp_path):
    repo_root = build_fixture(
        tmp_path / "repo",
        "def widget_other(size, color):\n    return {'size': size, 'color': color}\n",
    )
    report = run_verify(repo_root)
    assert field(report, "interface_drift") is True
    assert field(report, "overall") == "fail"


def test_extra_parameter_is_drift_and_fails(tmp_path):
    repo_root = build_fixture(
        tmp_path / "repo",
        "def widget_make(size, color, shape):\n"
        "    return {'size': size, 'color': color, 'shape': shape}\n",
    )
    report = run_verify(repo_root)
    assert field(report, "interface_drift") is True
    assert field(report, "overall") == "fail"


def test_matching_interface_is_not_drift(tmp_path):
    repo_root = build_fixture(
        tmp_path / "repo",
        "def widget_make(size, color):\n"
        "    return {'size': size, 'color': color}\n"
        "\n"
        "\n"
        "def extra_helper(x):\n"
        "    return x\n",
    )
    report = run_verify(repo_root)
    assert field(report, "interface_drift") is False