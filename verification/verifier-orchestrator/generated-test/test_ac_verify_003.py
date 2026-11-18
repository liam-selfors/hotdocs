# hotdocs-criterion: sha256:2a94a3243b852854f063cbf5c977114a65f0d73320d82729a423e723efeadbca
import json
import os
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"

CRITERION_TEXT = (
    "# AC-WIDGET-001\n"
    "\n"
    "Covers: R-WIDGET-001\n"
    "Kind: llm-judge\n"
    "\n"
    "```gherkin\n"
    "Given the widget component's spec\n"
    "When a reviewer reads its requirements\n"
    "Then they contain no contradiction\n"
    "```\n"
)

REQUIREMENT_TEXT = (
    "# R-WIDGET-001\n"
    "\n"
    "**R-WIDGET-001** — The widget spec MUST be free of contradictions.\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, log_dir):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "widget-capability.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget Capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widget Capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets exist.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widgets.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given a widget\n"
        "When it is inspected\n"
        "Then it is a widget\n"
        "```\n",
    )
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-WIDGET]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget is a fixture component.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widgets.\n"
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
    write(comp / "requirements" / (REQUIREMENT_ID + ".md"), REQUIREMENT_TEXT)
    write(comp / "acceptance" / (CRITERION_ID + ".md"), CRITERION_TEXT)
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nwidget_size(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # The component's own (empty) code.
    write(repo_root / "gen" / SLUG / "widget.py", "")

    assembler_log = log_dir / "assembler_calls.log"
    assembler_source = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(assembler_log)) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps([component_id, criterion_id]) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(REQUIREMENT_ID) + ",\n"
        "        'criterion_text': " + repr(CRITERION_TEXT) + ",\n"
        "        'requirement_text': " + repr(REQUIREMENT_TEXT) + ",\n"
        "        'interface': " + repr("# Library\n\nwidget_size(x: int) -> int") + ",\n"
        "        'glossary': " + repr("# Glossary\n\n- **Widget** — a test term.") + ",\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source,
    )

    # A tripwire stand-in for the model endpoint: if verify reaches for a
    # model through the repo's llm-endpoint, this records it.
    model_log = log_dir / "model_calls.log"
    endpoint_source = (
        "LOG = " + repr(str(model_log)) + "\n"
        "\n"
        "def complete(*args, **kwargs):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('complete called\\n')\n"
        "    raise RuntimeError('verify must not call a model itself')\n"
    )
    write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", endpoint_source)

    return model_log


def test_llm_judge_criterion_skipped_without_judge(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    model_log = build_fixture(repo_root, log_dir)

    # Remove any credentials so no real model could be reached either.
    for name in list(os.environ):
        if name.endswith("_API_KEY") or name.startswith("VAR_"):
            monkeypatch.delenv(name, raising=False)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1, criteria
    entry = matching[0]

    assert field(entry, "kind") == "llm-judge"
    assert field(entry, "result") == "skipped"
    assert "rationale" in entry, entry
    assert entry["rationale"] is None

    as_dict = report.to_dict()
    dict_entries = [c for c in as_dict["criteria"] if c["id"] == CRITERION_ID]
    assert len(dict_entries) == 1
    assert dict_entries[0]["result"] == "skipped"
    assert dict_entries[0].get("rationale", "missing") is None
    json.dumps(as_dict)

    # verify did not call a model itself to produce that result.
    assert not model_log.exists() or model_log.read_text(encoding="utf-8") == ""