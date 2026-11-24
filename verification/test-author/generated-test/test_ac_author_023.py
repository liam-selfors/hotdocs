# hotdocs-criterion: sha256:be0583154d14028697e7d8581bcbf3d68a75b5d4ddb9caee8da9c5ab9916e90b
import re

import test_author


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

REPLY_FILE = "def test_placeholder():\n    assert 1 + 1 == 2\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as handle:\n"
        "        handle.write('probe ' + repr(module_name) + '\\n')\n"
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
            "When make_widget(spec) is called\n"
            "Then a widget is returned"
        ),
        "requirement_text": "R-WIDGET-MAKER-001 - make_widget MUST return a widget.",
        "interface": "make_widget(spec: dict) -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_prompt_holds_write_time_window_precision_block(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    log_path = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, log_path)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(NONCE_RE, prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + REPLY_FILE
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
    assert "(`datetime.now(timezone.utc).replace(microsecond=0)`)" in first_prompt
    assert (
        "never comparing a timestamp truncated on write against "
        "microsecond-precision bounds."
    ) in first_prompt