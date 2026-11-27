# hotdocs-criterion: sha256:7094e4a24fa1fb66e293dca65c61717e7220679d5b48d10015dd7acc9c691e63
"""AC-VERIFY-004: interface drift between gen/<component>/ and interface/ fails verify."""

import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


INTERFACE_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "widget_area(width: int, height: int) -> int\n"
    "```\n"
    "\n"
    "`widget_area` returns the product of its two arguments.\n"
)

REQUIREMENT_TEXT = (
    "# R-WIDGET-001\n"
    "\n"
    "**R-WIDGET-001** \u2014 This component MUST provide `widget_area(width, height)`\n"
    "  returning `width * height`.\n"
)

CRITERION_TEXT = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: llm-judge\n"
    "\n"
    "```gherkin\n"
    "Given the widget interface documentation\n"
    "When a reviewer reads it\n"
    "Then widget_area is clearly documented\n"
    "```\n"
)

GLOSSARY_TEXT = "# Glossary\n\n- **Widget** \u2014 a rectangle with an area.\n"


def assembler_source(log_path):
    return (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(criterion_id + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-WIDGET-001',\n"
        "        'criterion_text': " + repr(CRITERION_TEXT) + ",\n"
        "        'requirement_text': " + repr(REQUIREMENT_TEXT) + ",\n"
        "        'interface': " + repr(INTERFACE_TEXT) + ",\n"
        "        'glossary': " + repr(GLOSSARY_TEXT) + ",\n"
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
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings)}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    return _Report()\n"
    )


def build_fixture(root, module_source):
    root = Path(root)
    comp = root / "specs" / "components" / "widget"
    write(
        comp / "component.md",
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
        "Computes the area of a widget.\n",
    )
    write(comp / "interface" / "library.md", INTERFACE_TEXT)
    write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT_TEXT)
    write(comp / "acceptance" / "AC-WIDGET-001.md", CRITERION_TEXT)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget areas\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# P-WIDGET\n"
        "\n"
        "Users can compute a widget's area.\n",
    )
    write(root / "specs" / "glossary.md", GLOSSARY_TEXT)

    write(root / "gen" / "widget" / "widget.py", module_source)

    log_path = root / "assembler.log"
    write(
        root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(log_path),
    )
    write(root / "gen" / "test-probe" / "test_probe.py", probe_source())
    return root


def judge_pass(bundle):
    return {"result": "pass", "rationale": "widget_area is documented."}


MATCHING_MODULE = (
    "def widget_area(width, height):\n"
    "    return width * height\n"
)

MISMATCHED_PARAMS_MODULE = (
    "def widget_area(width, depth):\n"
    "    return width * depth\n"
)

MISSING_CALLABLE_MODULE = (
    "def widget_volume(width, height, depth):\n"
    "    return width * height * depth\n"
)


def test_matching_interface_has_no_drift(tmp_path):
    root = build_fixture(tmp_path / "repo", MATCHING_MODULE)
    report = verifier_orchestrator.verify("comp-widget", root, judge=judge_pass)
    assert field(report, "interface_drift") is False
    assert report.to_dict()["interface_drift"] is False


def test_parameter_mismatch_is_drift_and_fails(tmp_path):
    root = build_fixture(tmp_path / "repo", MISMATCHED_PARAMS_MODULE)
    report = verifier_orchestrator.verify("comp-widget", root, judge=judge_pass)
    assert field(report, "interface_drift") is True
    assert field(report, "overall") == "fail"
    as_dict = report.to_dict()
    assert as_dict["interface_drift"] is True
    assert as_dict["overall"] == "fail"


def test_missing_callable_is_drift_and_fails(tmp_path):
    root = build_fixture(tmp_path / "repo", MISSING_CALLABLE_MODULE)
    report = verifier_orchestrator.verify("comp-widget", root, judge=judge_pass)
    assert field(report, "interface_drift") is True
    assert field(report, "overall") == "fail"


def test_cli_reports_drift_with_exit_1(tmp_path, capsys):
    root = build_fixture(tmp_path / "repo", MISMATCHED_PARAMS_MODULE)
    code = verifier_orchestrator.main(
        ["comp-widget", "--repo-root", str(root), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 1
    doc = json.loads(out)
    assert doc["interface_drift"] is True
    assert doc["overall"] == "fail"