# hotdocs-criterion: sha256:19c2c421ae7f3253297c08e4ad9b67f2f23558d42fa740e6c1032efcbbb600ec
import re
from pathlib import Path

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

GOOD_TEST = "def test_placeholder():\n    assert 1 + 1 == 2"


def write_probe_stand_in(repo_root, log_path):
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_recording_mock(recorded):
    def mock_backend(prompt, model=None, **params):
        recorded.append(prompt)
        matches = NONCE_RE.findall(prompt)
        nonce = matches[-1] if matches else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + GOOD_TEST
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return mock_backend


def test_prompt_contains_criterion_requirement_interface_and_glossary(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, probe_log)

    criterion_text = (
        "Given a widget blueprint ZEBRA-CRITERION-7731\n"
        "When make_widget is called\n"
        "Then the widget is returned with its blueprint name"
    )
    requirement_text = (
        "R-WIDGET-MAKER-001 OCELOT-REQUIREMENT-4410: the component MUST "
        "build a widget from a blueprint."
    )
    interface = (
        "# Library\n\n"
        "make_widget(blueprint: str) -> Widget  # PANGOLIN-INTERFACE-9902\n"
    )
    glossary = (
        "- **Widget** - a thing a widget maker makes; QUOKKA-GLOSSARY-2287."
    )

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": criterion_text,
        "requirement_text": requirement_text,
        "interface": interface,
        "glossary": glossary,
        "dependency_interfaces": {},
    }

    recorded = []
    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=make_recording_mock(recorded)
    )

    assert field(result, "model_call_error") is None
    assert len(recorded) >= 1, "the mock model was never called"

    first_prompt = recorded[0]
    assert isinstance(first_prompt, str)
    assert criterion_text in first_prompt
    assert requirement_text in first_prompt
    assert interface.strip() in first_prompt
    assert glossary in first_prompt

    for prompt in recorded:
        assert criterion_text in prompt
        assert requirement_text in prompt
        assert interface.strip() in prompt
        assert glossary in prompt