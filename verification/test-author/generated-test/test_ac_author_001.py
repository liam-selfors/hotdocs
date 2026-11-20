# hotdocs-criterion: sha256:3e5b6b7b6843d47e35c6607beb1660ae2edff240d780f1c12eb1715d34410e79
import re
from pathlib import Path

import test_author


CRITERION_TEXT = (
    "Given a widget blueprint zq7-alpha When make_widget is called "
    "Then the returned widget carries the blueprint marker zq7-alpha"
)
REQUIREMENT_TEXT = (
    "R-WIDGET-MAKER-001 The widget maker MUST stamp every widget with "
    "its blueprint marker, requirement-token rq9-bravo"
)
INTERFACE_TEXT = (
    "make_widget(blueprint: str) -> Widget  interface-token if4-charlie"
)
GLOSSARY_TEXT = (
    "Widget: a stamped artifact produced by the widget maker, "
    "glossary-token gl2-delta"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def test_prompt_contains_criterion_requirement_interface_and_glossary(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        nonces = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        n = nonces[-1] if nonces else "0" * 32
        body = "def test_placeholder():\n    assert True\n"
        text = "-----BEGIN FILE " + n + "-----\n" + body + "\n-----END FILE " + n + "-----"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": CRITERION_TEXT,
        "requirement_text": REQUIREMENT_TEXT,
        "interface": INTERFACE_TEXT,
        "glossary": GLOSSARY_TEXT,
        "dependency_interfaces": {},
    }

    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=mock_backend
    )

    assert result is not None
    assert len(recorded) >= 1, "the mock model was never called"

    first_prompt = recorded[0]
    assert isinstance(first_prompt, str)
    assert CRITERION_TEXT in first_prompt
    assert REQUIREMENT_TEXT in first_prompt
    assert INTERFACE_TEXT in first_prompt
    assert GLOSSARY_TEXT in first_prompt