# hotdocs-criterion: sha256:e875c8fb6f25fa8d47861bb8fdff1914beb26a8ff54bf28e30fa354611dd9499
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


TESTING_TEXT = "Write fixtures with write_fixture(repo_root)."

MOCK_TEST_FILE = (
    "import test_author\n"
    "\n"
    "\n"
    "def test_placeholder():\n"
    "    assert test_author.author_test is not None\n"
)


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
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def _make_mock(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
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

    return backend


def _bundle(testing):
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 The maker MUST make widgets.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "dependency_interfaces": {},
        "testing": testing,
    }


def _run(tmp_root, monkeypatch, testing):
    tmp_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_root)
    log_path = tmp_root / "probe_calls.log"
    _write_probe_stand_in(tmp_root, log_path)
    prompts = []
    result = test_author.author_test(
        _bundle(testing), "mock", repo_root=tmp_root, llm_backend=_make_mock(prompts)
    )
    return result, prompts


def test_prompt_includes_test_spec_when_testing_nonempty(tmp_path, monkeypatch):
    result, prompts = _run(tmp_path / "with_testing", monkeypatch, TESTING_TEXT)
    assert field(result, "model_call_error") is None
    assert prompts, "mock model was never called"
    first = prompts[0]
    assert "## Test spec" in first.splitlines()
    assert TESTING_TEXT in first


def test_prompt_omits_test_spec_when_testing_empty(tmp_path, monkeypatch):
    result, prompts = _run(tmp_path / "without_testing", monkeypatch, "")
    assert field(result, "model_call_error") is None
    assert prompts, "mock model was never called"
    first = prompts[0]
    assert "## Test spec" not in first