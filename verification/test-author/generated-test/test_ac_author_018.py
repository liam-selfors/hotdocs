# hotdocs-criterion: sha256:0e7093c9f58385d0e1aaee52144906e652c4cb8eb6d8511494e6cddcc7c709b4
import re
from pathlib import Path

import test_author


TARGET_LINE = (
    "- A unit file (`constraints.md`, or anything under `requirements/`, "
    "`interface/` or `acceptance/`) carries no frontmatter at all."
)

NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

GOOD_TEST = (
    "import test_author\n"
    "\n"
    "\n"
    "def test_something():\n"
    "    assert test_author.author_test is not None\n"
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
        "GATE_VERSION = 'test-probe@1.5.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
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
        "criterion_text": (
            "Given a widget spec\n"
            "When make_widget is called\n"
            "Then a widget is returned"
        ),
        "requirement_text": "R-WIDGET-MAKER-001 - make_widget MUST return a widget.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_prompt_holds_unit_file_frontmatter_rule_line(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, probe_log)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(NONCE_RE, prompt)[-1]
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

    result = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "model_call_error") is None
    assert len(prompts) >= 1

    first_prompt = prompts[0]
    assert TARGET_LINE in first_prompt.splitlines()