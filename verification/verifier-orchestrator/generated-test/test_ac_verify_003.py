import verifier_orchestrator

import json
import os
import socket
import subprocess
from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_field(value, name):
    if isinstance(value, dict):
        return name in value
    return hasattr(value, name)


GLOSSARY = """# Glossary

- **Widget** — a test term.
"""

COMPONENT_MD = """---
id: comp-widget
title: Widget
status: draft
owners: [team-a]
realizes: [P-WIDGET]
depends_on: []
---

# Widget

## Purpose

Widget triples a number.

## Scope

- In scope: tripling a number.
- Out of scope: everything else.

## Definitions

None.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

## Change log

- Initial draft.
"""

PRODUCT_MD = """---
id: P-WIDGET
title: Widgeting
status: draft
owners: [team-a]
---

# Widgeting

## Purpose

Users can triple numbers.

## Scope

- In scope: tripling numbers.

## Capability scenarios

### CS-WIDGET-001

Covers: P-WIDGET
Kind: llm-judge

```gherkin
Given a number to triple
When the user asks for it to be tripled
Then the answer is clearly three times the number
```
"""

REQUIREMENT_MD = """# R-WIDGET-001

**R-WIDGET-001** — `triple(x)` MUST be documented clearly enough that a reader understands it returns `3 * x`.
"""

ACCEPTANCE_MD = """# AC-WIDGET-001

Covers: R-WIDGET-001
Kind: llm-judge

```gherkin
Given the widget component's interface documentation
When a reviewer reads the description of triple
Then the reviewer understands that it returns three times its input
```
"""

LIBRARY_MD = """# Library

```
triple(x: int) -> int
```
"""

CONSTRAINTS_MD = """# Constraints

None.
"""

GEN_WIDGET_PY = """def triple(x):
    return 3 * x
"""


def _fake_assembler_source(log_path):
    return (
        "import json\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def _log(record):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(record) + '\\n')\n"
        "\n"
        "class _Bundle:\n"
        "    def __init__(self, **fields):\n"
        "        self.__dict__['_fields'] = dict(fields)\n"
        "    def __getattr__(self, name):\n"
        "        try:\n"
        "            return self.__dict__['_fields'][name]\n"
        "        except KeyError:\n"
        "            raise AttributeError(name)\n"
        "    def __getitem__(self, key):\n"
        "        return self.__dict__['_fields'][key]\n"
        "    def get(self, key, default=None):\n"
        "        return self.__dict__['_fields'].get(key, default)\n"
        "    def keys(self):\n"
        "        return self.__dict__['_fields'].keys()\n"
        "    def items(self):\n"
        "        return self.__dict__['_fields'].items()\n"
        "    def values(self):\n"
        "        return self.__dict__['_fields'].values()\n"
        "    def __iter__(self):\n"
        "        return iter(self.__dict__['_fields'])\n"
        "    def __len__(self):\n"
        "        return len(self.__dict__['_fields'])\n"
        "    def __contains__(self, key):\n"
        "        return key in self.__dict__['_fields']\n"
        "    def to_dict(self):\n"
        "        return dict(self.__dict__['_fields'])\n"
        "\n"
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log({'fn': 'assemble', 'component_id': component_id})\n"
        "    return _Bundle(\n"
        "        component_id=component_id,\n"
        "        spec_bundle_hash='sha256:' + '0' * 64,\n"
        "        spec='# Widget\\n\\nWidget triples a number.',\n"
        "        interface='# Library\\n\\ntriple(x: int) -> int',\n"
        "        constraints='# Constraints\\n\\nNone.',\n"
        "        dependency_interfaces={},\n"
        "        dependency_context={},\n"
        "        dependency_usage={},\n"
        "        vars={},\n"
        "        glossary='# Glossary',\n"
        "        hint_code=None,\n"
        "    )\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log({'fn': 'assemble_criterion', 'component_id': component_id, 'criterion_id': criterion_id})\n"
        "    return _Bundle(\n"
        "        component_id=component_id,\n"
        "        criterion_id=criterion_id,\n"
        "        covers='R-WIDGET-001',\n"
        "        criterion_text='Given the docs\\nWhen read\\nThen understood',\n"
        "        requirement_text='**R-WIDGET-001** — triple(x) MUST be documented.',\n"
        "        interface='# Library\\n\\ntriple(x: int) -> int',\n"
        "        glossary='# Glossary',\n"
        "        dependency_interfaces={},\n"
        "    )\n"
    )


def _fake_compiler_source(log_path):
    return (
        "import json\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "GATE_VERSION = 'criterion-compiler@1.0.0'\n"
        "\n"
        "def _log(record):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(record) + '\\n')\n"
        "\n"
        "class CompileReport:\n"
        "    def __init__(self, outputs, gate_version, summary):\n"
        "        self.outputs = outputs\n"
        "        self.gate_version = gate_version\n"
        "        self.summary = summary\n"
        "\n"
        "class ParsedCriterion:\n"
        "    def __init__(self, criterion_id=None, covers=None, kind=None, gherkin=None, file=None):\n"
        "        self.criterion_id = criterion_id\n"
        "        self.covers = covers\n"
        "        self.kind = kind\n"
        "        self.gherkin = gherkin\n"
        "        self.file = file\n"
        "\n"
        "class InterfaceSurface:\n"
        "    def __init__(self, functions=None, types=None, module_name=''):\n"
        "        self.functions = functions if functions is not None else {}\n"
        "        self.types = types if types is not None else {}\n"
        "        self.module_name = module_name\n"
        "\n"
        "def compile(component_id, repo_root, target='pytest', out_dir=None):\n"
        "    _log({'fn': 'compile', 'component_id': component_id})\n"
        "    return CompileReport(\n"
        "        outputs=[],\n"
        "        gate_version=GATE_VERSION,\n"
        "        summary={'compiled': 0, 'errors': 0, 'skipped_non_compiled_kind': 1},\n"
        "    )\n"
        "\n"
        "def compile_criterion(criterion, surface=None):\n"
        "    _log({'fn': 'compile_criterion'})\n"
        "    return {'status': 'error', 'message': 'line 1: not a compiled criterion'}\n"
    )


def _fake_test_author_source(log_path):
    return (
        "import json\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'fn': 'author_test', 'model': str(model)}) + '\\n')\n"
        "    return {\n"
        "        'component_id': 'comp-widget',\n"
        "        'criterion_id': 'AC-WIDGET-001',\n"
        "        'model': str(model),\n"
        "        'seed': seed,\n"
        "        'prompt_version': 'v1',\n"
        "        'cache_hit': False,\n"
        "        'file': None,\n"
        "        'model_call_error': 'fake test-author must never be called',\n"
        "    }\n"
    )


def _fake_generator_source(log_path):
    return (
        "import json\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "GATE_VERSION = 'generator@2.0.0'\n"
        "PROMPT_VERSION = 'v10'\n"
        "\n"
        "def generate(bundle, model, retry_feedback=None, *, repo_root=None, llm_backend=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'fn': 'generate', 'model': str(model)}) + '\\n')\n"
        "    return {\n"
        "        'component_id': 'comp-widget',\n"
        "        'spec_bundle_hash': 'sha256:' + '0' * 64,\n"
        "        'model': str(model),\n"
        "        'prompt_version': PROMPT_VERSION,\n"
        "        'cache_hit': False,\n"
        "        'files': {},\n"
        "        'model_call_error': 'fake generator must never be called',\n"
        "        'refused': None,\n"
        "        'retry_feedback': retry_feedback,\n"
        "    }\n"
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root, logs_dir):
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "widgeting.md", PRODUCT_MD)
    comp = repo_root / "specs" / "components" / "widget"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-WIDGET-001.md", ACCEPTANCE_MD)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(repo_root / "gen" / "widget" / "widget.py", GEN_WIDGET_PY)

    # Planted fake dependencies (flat-module shape).
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        _fake_assembler_source(logs_dir / "assembler.log"),
    )
    _write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        _fake_compiler_source(logs_dir / "compiler.log"),
    )
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        _fake_test_author_source(logs_dir / "model.log"),
    )
    _write(
        repo_root / "gen" / "generator" / "generator.py",
        _fake_generator_source(logs_dir / "model.log"),
    )


MODEL_CLIS = {"claude", "ollama"}


@pytest.fixture
def no_model_access(monkeypatch):
    """Record (and refuse) any network connection or model-CLI subprocess."""
    for key in (
        "ANTHROPIC_API_KEY",
        "VAR_ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    attempts = {"network": [], "model_cli": []}

    def fake_connect(self, address):
        attempts["network"].append(repr(address))
        raise OSError("network access blocked by test")

    def fake_connect_ex(self, address):
        attempts["network"].append(repr(address))
        return 111

    monkeypatch.setattr(socket.socket, "connect", fake_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", fake_connect_ex)

    real_popen = subprocess.Popen

    class RecordingPopen(real_popen):
        def __init__(self, args, *a, **kw):
            tokens = [args] if isinstance(args, (str, bytes, os.PathLike)) else list(args)
            for tok in tokens:
                text = os.fsdecode(tok) if isinstance(tok, (bytes, os.PathLike)) else str(tok)
                for piece in text.split():
                    if os.path.basename(piece) in MODEL_CLIS:
                        attempts["model_cli"].append(text)
            super().__init__(args, *a, **kw)

    monkeypatch.setattr(subprocess, "Popen", RecordingPopen)
    return attempts


def _read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.parametrize("pass_none_explicitly", [False, True])
def test_llm_judge_criterion_skipped_with_null_rationale_when_no_judge(
    tmp_path, monkeypatch, no_model_access, pass_none_explicitly
):
    repo_root = tmp_path / "repo"
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    repo_root.mkdir()
    _build_fixture(repo_root, logs_dir)
    monkeypatch.chdir(repo_root)

    if pass_none_explicitly:
        report = verifier_orchestrator.verify("comp-widget", repo_root, judge=None)
    else:
        report = verifier_orchestrator.verify("comp-widget", repo_root)

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == "AC-WIDGET-001"]
    assert len(matching) == 1, f"expected exactly one AC-WIDGET-001 entry, got {criteria!r}"
    entry = matching[0]

    assert field(entry, "result") == "skipped"
    assert has_field(entry, "rationale"), f"skipped llm-judge entry lacks a rationale field: {entry!r}"
    assert field(entry, "rationale") is None

    # verify does not call a model itself to produce that result.
    model_calls = _read_log(logs_dir / "model.log")
    assert model_calls == [], f"verify invoked a model-calling dependency: {model_calls!r}"
    assert no_model_access["network"] == [], (
        f"verify attempted network access: {no_model_access['network']!r}"
    )
    assert no_model_access["model_cli"] == [], (
        f"verify launched a model CLI: {no_model_access['model_cli']!r}"
    )