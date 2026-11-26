# hotdocs-criterion: sha256:1e1980adefb66b45fb5d9ee13e4a73543ec4baca4443de75ade4feea546f14fc
import re
from pathlib import Path

import test_author


LINE_RATIFIED = (
    "- A document with `status: ratified` also sets the placeholder "
    "`last_ratified_commit: 0000000`."
)
LINE_NO_YAML = (
    "- A test MUST NEVER `import yaml` or any other third-party package not "
    "already installed: it writes and parses frontmatter as plain text."
)

MOCK_TEST_FILE = "def test_placeholder():\n    assert True\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "class ProbeReport:\n"
        "    def __init__(self, ok, findings, tests_run, tests_reached):\n"
        "        self.ok = ok\n"
        "        self.findings = findings\n"
        "        self.tests_run = tests_run\n"
        "        self.tests_reached = tests_reached\n"
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
        "GATE_VERSION = 'test-probe@1.5.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None, drivers=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return ProbeReport(True, [], 1, 1)\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def test_prompt_holds_block_r_author_012(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    log_path = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, log_path)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonces = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        nonce = nonces[-1] if nonces else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + MOCK_TEST_FILE
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
        "requirement_text": "R-WIDGET-MAKER-001 — The maker MUST make widgets.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }

    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert result is not None
    assert len(prompts) >= 1, "mock model was never called"

    first_lines = prompts[0].splitlines()
    assert LINE_RATIFIED in first_lines
    assert LINE_NO_YAML in first_lines