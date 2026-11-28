# hotdocs-criterion: sha256:74292ec511777f14c0b34adcb1eb007901501913596bc0646b45e2277f881e28
import re

import test_author


EXPECTED_LINE = "        return value[name] if isinstance(value, dict) else getattr(value, name)"
EXPECTED_TEXT = "MUST use dual dict-or-attribute access, never one assumed shape:"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "class ProbeReport:\n"
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None, drivers=None, **kwargs):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as handle:\n"
        "        handle.write('probe\\n')\n"
        "    return ProbeReport()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def test_prompt_holds_dual_access_block(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget, When made, Then it exists.",
        "requirement_text": "R-WIDGET-MAKER-001 The maker MUST make widgets.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }

    prompts = []
    test_body = (
        "import widget_maker\n"
        "\n"
        "\n"
        "def test_make_widget():\n"
        "    assert widget_maker.make_widget('a') is not None\n"
    )

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + test_body
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert len(prompts) >= 1
    first_prompt = prompts[0]
    assert EXPECTED_LINE in first_prompt.splitlines()
    assert EXPECTED_TEXT in first_prompt