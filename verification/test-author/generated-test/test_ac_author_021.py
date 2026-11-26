# hotdocs-criterion: sha256:74d40c63e170f16e2290fdcf91cf0a1bf99e373e7c6ea7b6eaf571998d178e98
import re
from pathlib import Path

import test_author


EXPECTED_LINE = "        return value[name] if isinstance(value, dict) else getattr(value, name)"
EXPECTED_SUBSTRING = "MUST use dual dict-or-attribute access, never one assumed shape:"

MARKER_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = Path(repo_root) / "gen" / "test-probe"
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


def test_prompt_holds_block_r_author_021(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    log_path = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, log_path)

    recorded_prompts = []
    test_file = "def test_something():\n    assert True\n"

    def mock_backend(prompt, model, **params):
        recorded_prompts.append(prompt)
        nonce = re.findall(MARKER_RE, prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + test_file
            + "\n-----END FILE " + nonce + "-----"
        )
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
        "criterion_text": "Given a widget, When made, Then it exists.",
        "requirement_text": "R-WIDGET-MAKER-001 - The maker MUST make widgets.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }

    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "model_call_error") is None
    assert len(recorded_prompts) >= 1

    first_prompt = recorded_prompts[0]
    assert EXPECTED_LINE in first_prompt.splitlines()
    assert EXPECTED_SUBSTRING in first_prompt