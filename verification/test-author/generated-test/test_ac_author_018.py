# hotdocs-criterion: sha256:1a7a21d11b004a4ebd50521cc10c0994b826265f9962eecb4db2a6117d33b683
import re

import test_author


EXPECTED_LINE = (
    "- A unit file (`constraints.md`, or anything under `requirements/`, "
    "`interface/` or `acceptance/`) carries no frontmatter at all."
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def test_prompt_contains_unit_file_frontmatter_rule(tmp_path, monkeypatch):
    repo_root = tmp_path
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    prompts = []
    test_body = (
        "import widget_maker\n"
        "\n"
        "\n"
        "def test_something():\n"
        "    widget_maker.make()\n"
    )

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonces = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        nonce = nonces[-1] if nonces else "0" * 32
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

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget, When make() is called, Then a widget is returned.",
        "requirement_text": "R-WIDGET-MAKER-001 - make() MUST return a widget.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }

    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert result is not None
    assert len(prompts) >= 1
    first_prompt = prompts[0]
    assert EXPECTED_LINE in first_prompt.splitlines()