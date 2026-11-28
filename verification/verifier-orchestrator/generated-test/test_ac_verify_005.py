# hotdocs-criterion: sha256:71fb43d996f424ae99eac3cbd46b6cfc4f083f514d02f5120708f896c94f7c28
"""AC-VERIFY-005: a skipped llm-judge criterion alone never causes `fail`.

Given a component whose generated-test criterion passes, whose tests kill
every mutant (no mutation site, so mutation_score 1.0), with no interface
drift, and whose only llm-judge criterion is skipped (no judge injected),
verify's overall verdict is `pass`.
"""

from pathlib import Path

import verifier_orchestrator


SLUG = "widget"
COMPONENT_ID = "comp-widget"
GEN_CRITERION = "AC-WIDGET-001"
JUDGE_CRITERION = "AC-WIDGET-002"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def assembler_source():
    return (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-' + criterion_id[3:],\n"
        "        'criterion_text': 'Given a widget When it runs Then it passes',\n"
        "        'requirement_text': 'The widget MUST pass.',\n"
        "        'interface': '# Library',\n"
        "        'glossary': '# Glossary',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n"
    )


def probe_source():
    return (
        "class _ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings)}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    return _ProbeReport()\n"
    )


def acceptance_text(criterion_id, covers, kind, gherkin):
    return (
        "# " + criterion_id + "\n"
        "\n"
        "Covers: " + covers + "\n"
        "Kind: " + kind + "\n"
        "\n"
        "```gherkin\n"
        + gherkin +
        "```\n"
    )


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a fixture thing.\n",
    )
    write(
        repo_root / "specs" / "product" / "widget-capability.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [fixture-team]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "A fixture capability.\n",
    )
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [fixture-team]\n"
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
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — The widget MUST pass its test.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-002.md",
        "# R-WIDGET-002\n\n**R-WIDGET-002** — The widget spec MUST be clear.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\nThe module declares no public functions.\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / (GEN_CRITERION + ".md"),
        acceptance_text(
            GEN_CRITERION,
            "R-WIDGET-001",
            "generated-test",
            "Given a widget fixture\n"
            "When its test runs\n"
            "Then the test passes\n",
        ),
    )
    write(
        comp / "acceptance" / (JUDGE_CRITERION + ".md"),
        acceptance_text(
            JUDGE_CRITERION,
            "R-WIDGET-002",
            "llm-judge",
            "Given the widget spec\n"
            "When a reviewer reads it\n"
            "Then it is clear\n",
        ),
    )
    # Code under test: empty module, so it has no mutation site.
    write(repo_root / "gen" / SLUG / "widget.py", "")
    # Dependency stand-ins.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source())


def make_test_author(log_path):
    content = (
        "def test_widget_passes():\n"
        "    assert 1 + 1 == 2\n"
    )

    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        criterion_id = bundle["criterion_id"] if isinstance(bundle, dict) else getattr(bundle, "criterion_id")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": criterion_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": content,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return test_author


def test_skipped_llm_judge_alone_does_not_fail(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        COMPONENT_ID,
        repo_root,
        judge=None,
        test_author=make_test_author(log_path),
    )

    criteria = {field(c, "id"): c for c in field(report, "criteria")}

    # Given: the generated-test criterion passes, the llm-judge one is skipped.
    assert field(criteria[GEN_CRITERION], "kind") == "generated-test"
    assert field(criteria[GEN_CRITERION], "result") == "pass", criteria[GEN_CRITERION]
    assert field(criteria[JUDGE_CRITERION], "kind") == "llm-judge"
    assert field(criteria[JUDGE_CRITERION], "result") == "skipped", criteria[JUDGE_CRITERION]
    for c in criteria.values():
        if field(c, "kind") in ("compiled", "generated-test"):
            assert field(c, "result") == "pass", c

    # Given: every mutant killed, no interface drift.
    assert field(report, "mutation_score") == 1.0
    assert field(report, "interface_drift") is False

    # The test author stand-in was actually used.
    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").count("called") >= 1

    # Then: the overall verdict is pass.
    assert field(report, "overall") == "pass"
    assert report.to_dict()["overall"] == "pass"