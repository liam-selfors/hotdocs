# hotdocs-criterion: sha256:4345764e740a6481f76b04806f66acd73d8c6cbd7479c3fa3bb524e883e7a6b9
"""AC-VERIFY-012: verify invokes an llm-judge criterion's judge exactly once (R-VERIFY-003)."""

from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
MODULE = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"
CAPABILITY_ID = "P-WIDGET"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def assembler_source():
    bundle = {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQUIREMENT_ID,
        "criterion_text": "Given the widget spec\nWhen a reviewer reads it\nThen it is clear",
        "requirement_text": "**" + REQUIREMENT_ID + "** - The widget spec MUST be clear.",
        "interface": "# Library\n\nwidget_value() -> int",
        "glossary": "# Glossary",
        "dependency_interfaces": {},
        "testing": "",
    }
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    bundle = dict(" + repr(bundle) + ")\n"
        "    bundle['component_id'] = component_id\n"
        "    bundle['criterion_id'] = criterion_id\n"
        "    return bundle\n"
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


def build_fixture(repo_root):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Widget** - a thing.\n")
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: " + CAPABILITY_ID + "\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [widget-team]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "The product offers a widget.\n",
    )
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [widget-team]\n"
        "depends_on: []\n"
        "realizes: [" + CAPABILITY_ID + "]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provides a widget value.\n",
    )
    write(
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "# " + REQUIREMENT_ID + "\n"
        "\n"
        "**" + REQUIREMENT_ID + "** - The widget spec MUST be clear.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "widget_value() -> int\n"
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
        "Given the widget spec\n"
        "When a reviewer reads it\n"
        "Then it is clear\n"
        "```\n",
    )
    write(repo_root / "gen" / SLUG / (MODULE + ".py"), "")
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source())


def make_judge(log_path):
    def judge(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {"result": "pass", "rationale": "The spec is clear."}

    return judge


def test_llm_judge_called_exactly_once(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    log_path = tmp_path / "judge.log"
    judge = make_judge(log_path)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, judge=judge)
    assert report is not None

    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert calls == ["called"], "judge was called " + repr(len(calls)) + " times, expected exactly 1"

    criteria = field(report, "criteria")
    ids = [field(c, "id") for c in criteria]
    assert ids.count(CRITERION_ID) == 1