# hotdocs-criterion: sha256:e7fb724d2f847ec83e1c2c745d0593b458701079bd64c2fb20dd0c671a36bf55
"""AC-VERIFY-004: a gen/<component>/ public interface that does not match its
interface/ contract makes interface_drift true and the overall verdict fail.

Covers R-VERIFY-004.
"""

from pathlib import Path

import verifier_orchestrator


SLUG = "widget-maker"
COMPONENT_ID = "comp-widget-maker"
MODULE = "widget_maker"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"
FENCE = "```"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def interface_text():
    return (
        "# Library\n"
        "\n"
        + FENCE + "\n"
        "compute(a: int, b: int) -> int\n"
        + FENCE + "\n"
        "\n"
        "`compute` adds its two arguments.\n"
    )


def criterion_text():
    return (
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        + FENCE + "gherkin\n"
        "Given two numbers\n"
        "When compute is called with them\n"
        "Then it returns a number\n"
        + FENCE + "\n"
    )


def requirement_text():
    return (
        "# " + REQUIREMENT_ID + "\n"
        "\n"
        "**" + REQUIREMENT_ID + "** — This component MUST provide `compute`.\n"
    )


def glossary_text():
    return "# Glossary\n\n- **Widget** — a thing this fixture makes.\n"


def assembler_source():
    return (
        "CRITERION_TEXT = " + repr(criterion_text()) + "\n"
        "REQUIREMENT_TEXT = " + repr(requirement_text()) + "\n"
        "INTERFACE_TEXT = " + repr(interface_text()) + "\n"
        "GLOSSARY_TEXT = " + repr(glossary_text()) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(REQUIREMENT_ID) + ",\n"
        "        'criterion_text': CRITERION_TEXT,\n"
        "        'requirement_text': REQUIREMENT_TEXT,\n"
        "        'interface': INTERFACE_TEXT,\n"
        "        'glossary': GLOSSARY_TEXT,\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n"
    )


def probe_source():
    return (
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings)}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    return ProbeReport()\n"
    )


def build_fixture(repo_root, module_source):
    comp_dir = repo_root / "specs" / "components" / SLUG
    write(
        comp_dir / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget Maker\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget Maker\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Makes widgets for the drift test.\n",
    )
    write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    write(comp_dir / "requirements" / (REQUIREMENT_ID + ".md"), requirement_text())
    write(comp_dir / "acceptance" / (CRITERION_ID + ".md"), criterion_text())
    write(comp_dir / "interface" / "library.md", interface_text())
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widgets\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Widgets\n"
        "\n"
        "Users get widgets.\n",
    )
    write(repo_root / "specs" / "glossary.md", glossary_text())

    # The code under test.
    write(repo_root / "gen" / SLUG / (MODULE + ".py"), module_source)

    # Stand-ins for dependencies verify / test-supply load from repo_root.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source())


def make_test_author(log_path):
    def test_author_stand_in(bundle):
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write("called\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/" + SLUG + "/generated-test/test_ac_widget_001.py",
                "content": "def test_ok():\n    assert True\n",
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return test_author_stand_in


def run_verify(repo_root):
    log_path = repo_root / "test_author.log"
    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, judge=None, test_author=make_test_author(log_path)
    )
    return report


def test_parameter_mismatch_is_interface_drift_and_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(
        repo_root,
        "def compute(a, c):\n"
        "    return a + c\n",
    )

    report = run_verify(repo_root)

    assert field(report, "interface_drift") is True
    assert field(report, "overall") == "fail"


def test_missing_callable_is_interface_drift_and_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(
        repo_root,
        "def other(a, b):\n"
        "    return a + b\n",
    )

    report = run_verify(repo_root)

    assert field(report, "interface_drift") is True
    assert field(report, "overall") == "fail"


def test_matching_interface_is_not_drift(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(
        repo_root,
        "def compute(a, b):\n"
        "    return a + b\n"
        "\n"
        "\n"
        "def helper(x):\n"
        "    return x\n",
    )

    report = run_verify(repo_root)

    # An undocumented extra public name is never drift (D84).
    assert field(report, "interface_drift") is False