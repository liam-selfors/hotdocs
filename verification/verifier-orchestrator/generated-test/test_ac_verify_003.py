# hotdocs-criterion: sha256:ac823da7e72eb2bfd2dae523b4be3821c06fb502baf32226163a2b24b22889f5
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


def build_fixture(repo_root, logs):
    comp = repo_root / "specs" / "components" / SLUG

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
        "Widgets exist.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- Widgets.\n",
    )

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
        "A widget component whose spec is judged for clarity.\n"
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
        "- Initial draft.\n",
    )

    write(
        comp / "requirements" / (REQUIREMENT_ID + ".md"),
        "# " + REQUIREMENT_ID + "\n"
        "\n"
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
        "Given the widget spec\n"
        "When a reviewer reads it\n"
        "Then it states its behavior without contradiction\n"
        "```\n",
    )

    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "make_widget(name: str) -> dict\n"
        "```\n",
    )

    write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    # The component's own (empty) code.
    write(repo_root / "gen" / SLUG / "widget.py", "")

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "LOG = " + repr(str(logs["assembler"])) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(str(criterion_id) + '\\n')\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'criterion_id': criterion_id,\n"
        "        'covers': " + repr(REQUIREMENT_ID) + ",\n"
        "        'criterion_text': 'Given the widget spec',\n"
        "        'requirement_text': 'The widget spec MUST be clear.',\n"
        "        'interface': 'make_widget(name: str) -> dict',\n"
        "        'glossary': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'testing': '',\n"
        "    }\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    return {\n"
        "        'component_id': component_id,\n"
        "        'spec_bundle_hash': 'sha256:' + '0' * 64,\n"
        "        'spec': '',\n"
        "        'interface': '',\n"
        "        'constraints': '',\n"
        "        'dependency_interfaces': {},\n"
        "        'dependency_context': {},\n"
        "        'dependency_usage': {},\n"
        "        'vars': {},\n"
        "        'glossary': '',\n"
        "        'hint_code': None,\n"
        "    }\n",
    )

    # test-probe stand-in: always ok.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "class _Report:\n"
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
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return _Report()\n",
    )

    # Model-calling stand-ins that log any call, so a call from verify is visible.
    write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        "LOG = " + repr(str(logs["model"])) + "\n"
        "\n"
        "\n"
        "def complete(*args, **kwargs):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write('complete\\n')\n"
        "    raise RuntimeError('no model may be called')\n",
    )
    write(
        repo_root / "gen" / "test-author" / "test_author.py",
        "LOG = " + repr(str(logs["model"])) + "\n"
        "GATE_VERSION = 'generated_test@3.0.0'\n"
        "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write('author_test\\n')\n"
        "    raise RuntimeError('no model may be called')\n",
    )


def test_llm_judge_criterion_skipped_without_judge(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    logs = {
        "assembler": log_dir / "assembler.log",
        "model": log_dir / "model.log",
    }
    build_fixture(repo_root, logs)

    # No credentials for any model provider.
    for name in (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "VAR_ANTHROPIC_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    # Record (and refuse) any in-process network connection, as a model call would need.
    network_attempts = []
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def guarded_connect(self, address):
        if getattr(socket, "AF_UNIX", None) is not None and self.family == socket.AF_UNIX:
            return real_connect(self, address)
        network_attempts.append(repr(address))
        raise OSError("network disabled in test")

    def guarded_connect_ex(self, address):
        if getattr(socket, "AF_UNIX", None) is not None and self.family == socket.AF_UNIX:
            return real_connect_ex(self, address)
        network_attempts.append(repr(address))
        raise OSError("network disabled in test")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1, criteria
    entry = matching[0]

    assert field(entry, "kind") == "llm-judge"
    assert field(entry, "result") == "skipped"
    if isinstance(entry, dict):
        assert "rationale" in entry
    assert field(entry, "rationale") is None

    # verify did not call a model itself to produce that result.
    assert network_attempts == []
    model_log = logs["model"]
    assert not model_log.exists() or model_log.read_text(encoding="utf-8") == ""