# hotdocs-criterion: sha256:190f0fa7e1df7528a06a3d88af352981b66a479c6c89a3cb0dac2ade71d2c178
import socket
from pathlib import Path

import verifier_orchestrator


SLUG = "widget"
COMPONENT_ID = "comp-widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root, log_path):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a thing under test.\n",
    )
    write(
        repo_root / "specs" / "product" / "widget-capability.md",
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
        "Provide widgets.\n",
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
        "**" + REQUIREMENT_ID + "** — The widget documentation MUST be clear.\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n\n```\nmake_widget(name: str) -> str\n```\n",
    )
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the widget documentation\n"
        "When a reader reads it\n"
        "Then it is clear and free of contradiction\n"
        "```\n",
    )
    write(repo_root / "gen" / SLUG / "widget.py", "")

    log = repr(str(log_path))

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "def _log(name):\n"
        "    with open(" + log + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(name + '\\n')\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log('assemble_criterion')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(REQUIREMENT_ID) + ",\n"
        "        'criterion_text': 'Given the widget documentation',\n"
        "        'requirement_text': 'The widget documentation MUST be clear.',\n"
        "        'interface': 'make_widget(name: str) -> str',\n"
        "        'glossary': 'Widget',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n",
    )
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "GATE_VERSION = 'test-probe@1.4.0'\n"
        "\n"
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
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    return ProbeReport()\n",
    )
    # Logging stand-ins for every model-calling dependency: any call means
    # verify tried to call a model itself.
    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "def _log(name):\n"
        "    with open(" + log + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(name + '\\n')\n"
        "\n"
        "\n"
        "def complete(*args, **kwargs):\n"
        "    _log('llm_endpoint.complete')\n"
        "    raise RuntimeError('no model call allowed')\n",
    )
    write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "GATE_VERSION = 'generated_test@3.0.0'\n"
        "\n"
        "\n"
        "def _log(name):\n"
        "    with open(" + log + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(name + '\\n')\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    _log('test_author.author_test')\n"
        "    raise RuntimeError('no model call allowed')\n",
    )


def test_llm_judge_criterion_skipped_without_judge(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "calls.log"
    build_fixture(repo_root, log_path)

    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    network_attempts = []
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def guarded_connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            network_attempts.append(address)
            raise OSError("network access is forbidden in this test")
        return original_connect(self, address)

    def guarded_connect_ex(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            network_attempts.append(address)
            raise OSError("network access is forbidden in this test")
        return original_connect_ex(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, judge=None)

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1, criteria
    entry = matching[0]
    assert field(entry, "kind") == "llm-judge"
    assert field(entry, "result") == "skipped"
    if isinstance(entry, dict):
        assert "rationale" in entry
    assert field(entry, "rationale") is None

    as_dict = report.to_dict()
    dict_entries = [c for c in as_dict["criteria"] if c["id"] == CRITERION_ID]
    assert len(dict_entries) == 1
    assert dict_entries[0]["result"] == "skipped"
    assert "rationale" in dict_entries[0]
    assert dict_entries[0]["rationale"] is None

    calls = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    model_calls = [c for c in calls if c in ("llm_endpoint.complete", "test_author.author_test")]
    assert model_calls == []
    assert network_attempts == []