# hotdocs-criterion: sha256:2a94a3243b852854f063cbf5c977114a65f0d73320d82729a423e723efeadbca
import os
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


CRITERION_TEXT = (
    "Given a widget is 3\n"
    "When widget_size is invoked with [widget]\n"
    "Then the widget spec reads clearly and without contradiction"
)
REQUIREMENT_TEXT = "**R-WIDGET-001** — `widget_size(x)` MUST be documented clearly."


def build_fixture(repo_root, log_dir):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets are sized.\n",
    )
    comp = repo_root / "specs" / "components" / "widget"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget sizes a number.\n",
    )
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n" + REQUIREMENT_TEXT + "\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n" + CRITERION_TEXT + "\n```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nwidget_size(x: int) -> int\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # The component's own (empty) generated code.
    write(repo_root / "gen" / "widget" / "widget.py", "")

    # Fake spec-bundle-assembler: assemble_criterion returns a full CriterionBundle mapping.
    assembler_log = log_dir / "assembler.log"
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(" + repr(str(assembler_log)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(str(criterion_id) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-WIDGET-001',\n"
        "        'criterion_text': " + repr(CRITERION_TEXT) + ",\n"
        "        'requirement_text': " + repr(REQUIREMENT_TEXT) + ",\n"
        "        'interface': '# Library\\n\\nwidget_size(x: int) -> int',\n"
        "        'glossary': '# Glossary\\n\\n- **Widget** — a test term.',\n"
        "        'dependency_interfaces': {},\n"
        "    }\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    raise RuntimeError('assemble is not expected to be called')\n",
    )

    # Tripwires: any model-calling dependency verify might reach for logs its call.
    model_log = log_dir / "model_calls.log"
    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def complete(*args, **kwargs):\n"
        "    with open(" + repr(str(model_log)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('llm-endpoint.complete\\n')\n"
        "    raise RuntimeError('verify must not call a model itself')\n",
    )
    write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "GATE_VERSION = 'generated_test@1.2.0'\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(" + repr(str(model_log)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('test-author.author_test\\n')\n"
        "    raise RuntimeError('verify must not call a model itself')\n",
    )
    return assembler_log, model_log


def test_llm_judge_criterion_skipped_without_judge(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    assembler_log, model_log = build_fixture(repo_root, log_dir)

    # Make sure no real model credentials are available either.
    for name in list(os.environ):
        if name.endswith("API_KEY"):
            monkeypatch.delenv(name, raising=False)

    report = verifier_orchestrator.verify("comp-widget", repo_root)

    criteria = field(report, "criteria")
    matching = [c for c in criteria if c["id"] == "AC-WIDGET-001"]
    assert len(matching) == 1
    entry = matching[0]
    assert entry["kind"] == "llm-judge"
    assert entry["result"] == "skipped"
    assert "rationale" in entry
    assert entry["rationale"] is None

    calls = model_log.read_text(encoding="utf-8") if model_log.exists() else ""
    assert calls == ""