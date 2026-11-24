# hotdocs-criterion: sha256:64bfca49ef4c954fd6e57ecebf36c81540b50f032555067d5199f2e623d91645
import re
from pathlib import Path

import test_author


LINE_RATIFIED = "- A document with `status: ratified` also sets the placeholder `last_ratified_commit: 0000000`."
LINE_NO_YAML = "- A test MUST NEVER `import yaml` or any other third-party package not already installed: it writes and parses frontmatter as plain text."

GOOD_TEST = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_widget():\n"
    "    assert widget_maker.make() is not None\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_probe_stand_in(repo_root, log_path):
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
        "GATE_VERSION = 'test-probe@1.4.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None, assets=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen make() is called\nThen a widget is returned",
        "requirement_text": "R-WIDGET-MAKER-001 - make() MUST return a widget.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_prompt_holds_block_r_author_012_lines(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, probe_log)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonces = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        n = nonces[-1] if nonces else "0" * 32
        text = "-----BEGIN FILE " + n + "-----\n" + GOOD_TEST + "\n-----END FILE " + n + "-----"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert result is not None
    assert field(result, "model_call_error") is None
    assert len(prompts) >= 1

    lines = prompts[0].splitlines()
    assert LINE_RATIFIED in lines
    assert LINE_NO_YAML in lines