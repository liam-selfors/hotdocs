# hotdocs-criterion: sha256:e720fc445d0866afd1532008783aa9fa23165426d8db981a4bbfc2fa8cd9b538
import re

import test_author


LINE_RATIFIED = (
    "- A document with `status: ratified` also sets the placeholder "
    "`last_ratified_commit: 0000000`."
)
LINE_NO_YAML = (
    "- A test MUST NEVER `import yaml` or any other third-party package not "
    "already installed: it writes and parses frontmatter as plain text."
)

GOOD_TEST = (
    "import test_author\n"
    "\n"
    "\n"
    "def test_placeholder():\n"
    "    assert test_author is not None\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 0\n"
        "        self.tests_reached = 0\n"
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
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return ProbeReport()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget, When made, Then it exists.",
        "requirement_text": "R-WIDGET-MAKER-001 The maker MUST make widgets.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_prompt_holds_fixture_frontmatter_rule_lines(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, probe_log)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
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

    lines = prompts[0].splitlines()
    assert LINE_RATIFIED in lines
    assert LINE_NO_YAML in lines