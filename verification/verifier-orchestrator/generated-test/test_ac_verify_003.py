# hotdocs-criterion: sha256:1b8cfe049de2ed3fdb999cade1089058de5b90b6a78de955a1ffb0e3724cd0b9
import os
import socket
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, assembler_log, probe_log, llm_log):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a thing under test.\n",
    )
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Provide widgets.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- Widgets.\n",
    )
    comp = repo_root / "specs" / "components" / SLUG
    write(
        comp / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [test-team]\n"
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
    write(
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "**" + REQUIREMENT_ID + "** — The widget spec MUST be clear.\n",
    )
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given a widget spec\n"
        "When a reviewer reads it\n"
        "Then it reads clearly\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nmake_widget(name: str) -> str\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(repo_root / "gen" / SLUG / "widget.py", "")

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "LOG = " + repr(str(assembler_log)) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(str(criterion_id) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(REQUIREMENT_ID) + ",\n"
        "        'criterion_text': 'Given a widget spec',\n"
        "        'requirement_text': 'The widget spec MUST be clear.',\n"
        "        'interface': 'make_widget(name: str) -> str',\n"
        "        'glossary': 'Widget',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n",
    )

    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "LOG = " + repr(str(probe_log)) + "\n"
        "\n"
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return ProbeReport()\n",
    )

    # Tripwire: if verify reached for a model endpoint of its own, this logs it.
    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "LOG = " + repr(str(llm_log)) + "\n"
        "\n"
        "def complete(*args, **kwargs):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('complete\\n')\n"
        "    raise RuntimeError('model must not be called')\n",
    )


def test_llm_judge_criterion_skipped_without_judge(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    assembler_log = logs / "assembler.log"
    probe_log = logs / "probe.log"
    llm_log = logs / "llm.log"
    author_log = logs / "author.log"
    build_fixture(repo_root, assembler_log, probe_log, llm_log)

    for name in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    connections = []

    def blocked_connect(self, address, *args, **kwargs):
        connections.append(address)
        raise OSError("network blocked by test")

    def blocked_create_connection(address, *args, **kwargs):
        connections.append(address)
        raise OSError("network blocked by test")

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked_connect)
    monkeypatch.setattr(socket, "create_connection", blocked_create_connection)

    def test_author_stub(bundle):
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write("author\n")
        return {
            "model": "none",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": {"category": "unexpected", "message": "must not be called"},
            "file": None,
        }

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, judge=None, test_author=test_author_stub
    )

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1, criteria
    entry = matching[0]

    assert field(entry, "kind") == "llm-judge"
    assert field(entry, "result") == "skipped"
    if isinstance(entry, dict):
        assert "rationale" in entry
        assert entry["rationale"] is None
    else:
        assert getattr(entry, "rationale") is None

    # verify did not call a model itself to produce the result.
    assert not llm_log.exists() or llm_log.read_text(encoding="utf-8") == ""
    assert not author_log.exists() or author_log.read_text(encoding="utf-8") == ""
    assert connections == []