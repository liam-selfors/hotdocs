# hotdocs-criterion: sha256:93261f74864ca7223fd9479113e7068d3beaa22f3009fdb911c02076531b5465
"""AC-VERIFY-003: an llm-judge criterion with no judge configured is skipped,
with a null rationale, and verify makes no model call of its own to produce it."""

import os
import stat
import sys
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_log(path):
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def assembler_source(log_path):
    return (
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('assemble_criterion ' + str(criterion_id) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': 'R-WIDGET-001',\n"
        "        'criterion_text': 'Given the widget interface text When a reviewer reads it Then it is clear',\n"
        "        'requirement_text': 'The widget interface documentation MUST be clear.',\n"
        "        'interface': 'make_widget(name)',\n"
        "        'glossary': 'Glossary.',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n"
    )


def model_stub_source(log_path, func_name, label):
    return (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "def " + func_name + "(*args, **kwargs):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(" + repr(label) + " + '\\n')\n"
        "    raise RuntimeError(" + repr(label + " must not be called") + ")\n"
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
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    return _Report()\n"
    )


def build_fixture(repo_root, logs):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\nGlossary.\n")
    write(
        repo_root / "specs" / "product" / "widget-cap.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "Users can make widgets.\n",
    )
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
        "Makes widgets.\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n"
        "\n"
        "**R-WIDGET-001** — The widget interface documentation MUST be clear.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nmake_widget(name)\n```\n",
    )
    write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the widget interface text\n"
        "When a reviewer reads it\n"
        "Then it is clear\n"
        "```\n",
    )
    # Code under test: empty module, no tests import it.
    write(repo_root / "gen" / "widget" / "widget.py", "")

    # Stand-ins for dependencies.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_source(logs["assembler"]),
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_source())
    # Any model-calling module verify might reach: each logs and raises.
    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        model_stub_source(logs["model"], "complete", "llm_endpoint.complete"),
    )
    write(
        repo_root / "gen" / "test-author" / "test_author.py",
        model_stub_source(logs["model"], "author_test", "test_author.author_test")
        + "\nGATE_VERSION = 'generated_test@3.0.0'\n",
    )


def fake_cli_bin(bin_dir, log_path):
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in ("claude", "ollama"):
        script = bin_dir / name
        script.write_text(
            "#!/bin/sh\n"
            "echo " + name + " >> " + str(log_path) + "\n"
            "exit 1\n",
            encoding="utf-8",
        )
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_llm_judge_criterion_skipped_without_judge(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = {
        "assembler": tmp_path / "assembler.log",
        "model": tmp_path / "model.log",
    }
    build_fixture(repo_root, logs)

    # No credentials for any provider, and model CLIs on PATH that log if run.
    for var in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    bin_dir = tmp_path / "bin"
    fake_cli_bin(bin_dir, logs["model"])
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))

    report = verifier_orchestrator.verify("comp-widget", repo_root)

    criteria = list(field(report, "criteria"))
    matching = [c for c in criteria if field(c, "id") == "AC-WIDGET-001"]
    assert len(matching) == 1, criteria
    entry = matching[0]

    assert field(entry, "kind") == "llm-judge"
    assert field(entry, "result") == "skipped"
    if isinstance(entry, dict):
        assert "rationale" in entry, entry
    assert field(entry, "rationale") is None

    # verify did not call a model itself to produce that result.
    assert read_log(logs["model"]) == []