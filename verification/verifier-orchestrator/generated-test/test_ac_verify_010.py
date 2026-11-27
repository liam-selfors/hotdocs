# hotdocs-criterion: sha256:b779373dc24881b933e72b9275196ddc522f7e0ed6f0c1f3921beaaa6fc6922a
"""AC-VERIFY-010: a generated-test criterion with no cached test and no
test_author configured is recorded as fail (failure_origin "test"), never
skipped, and the overall verdict is fail (R-VERIFY-010)."""

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
    "        'criterion_text': 'Given a widget When it is checked Then it exists',\n"
    "        'requirement_text': 'The widget MUST exist.',\n"
    "        'interface': 'make_widget(x)',\n"
    "        'glossary': '',\n"
    "        'dependency_interfaces': {},\n"
    "        'testing': '',\n"
    "    }\n"
)

PROBE_SOURCE = (
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


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "widget"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team]\n"
        "depends_on: []\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component.\n",
    )
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# P-WIDGET\n"
        "\n"
        "A fixture capability.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — The widget MUST exist.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nmake_widget(x)\n```\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it is checked\n"
        "Then it exists\n"
        "```\n",
    )
    write(repo_root / "gen" / "widget" / "widget.py", "")
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        ASSEMBLER_SOURCE,
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", PROBE_SOURCE)


def test_generated_test_without_cache_or_author_fails(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    cached = (
        repo_root / "verification" / "widget" / "generated-test" / "test_ac_widget_001.py"
    )
    assert not cached.exists()

    report = verifier_orchestrator.verify("comp-widget", repo_root)

    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == "AC-WIDGET-001"]
    assert len(matches) == 1, criteria
    entry = matches[0]

    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") != "skipped"
    assert field(entry, "result") == "fail"
    assert field(entry, "failure_origin") == "test"

    assert field(report, "overall") == "fail"