# hotdocs-criterion: sha256:aea07dab335418745a53d427fba2165a819f0ca756f1e9e0f57583c100d38ced
import re

import pytest

import test_author


GEN_SENTINEL = "GENSENTINELQ7X9Z3VK"
GEN_SENTINEL_FUNC = "gen_only_helper_q7x9z3vk"
INTERFACE_MARKER = "IFACEMARKERW4P8L2"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    src = (
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(repr(criterion_bundle).replace('\\n', ' ') + ' || ' + repr(test_source).replace('\\n', ' ') + '\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(src, encoding="utf-8")


def _write_component_gen_code(repo_root):
    gen_dir = repo_root / "gen" / "widget-maker"
    gen_dir.mkdir(parents=True, exist_ok=True)
    src = (
        "# " + GEN_SENTINEL + "\n"
        "SECRET_IMPL = " + repr(GEN_SENTINEL) + "\n"
        "\n"
        "\n"
        "def " + GEN_SENTINEL_FUNC + "():\n"
        "    return SECRET_IMPL\n"
        "\n"
        "\n"
        "def make():\n"
        "    return " + GEN_SENTINEL_FUNC + "()\n"
    )
    (gen_dir / "widget_maker.py").write_text(src, encoding="utf-8")
    (gen_dir / "notes.txt").write_text(GEN_SENTINEL + " notes\n", encoding="utf-8")


def test_criterion_bundle_carries_no_gen_component_content(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    _write_component_gen_code(repo_root)
    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - make() MUST return a widget.",
        "interface": "# Library\n\nmake() -> str  " + INTERFACE_MARKER + "\n",
        "glossary": "",
        "dependency_interfaces": {},
    }

    prompts = []
    test_body = "import widget_maker\n\n\ndef test_make():\n    assert widget_maker.make()\n"

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + test_body
            + "\n-----END FILE " + nonce + "-----"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "model_call_error") is None
    assert prompts, "the model was never called"

    # Positive control: the bundle's interface content does reach the prompt.
    assert any(INTERFACE_MARKER in p for p in prompts)

    # No prompt contains anything derived from gen/widget-maker/ content.
    for p in prompts:
        assert GEN_SENTINEL not in p
        assert GEN_SENTINEL_FUNC not in p
        assert "SECRET_IMPL" not in p

    # The bundle handed on to test-probe carries no gen/ content either.
    assert probe_log.is_file(), "test-probe stand-in was never called"
    log_text = probe_log.read_text(encoding="utf-8")
    assert log_text.strip()
    assert GEN_SENTINEL not in log_text
    assert GEN_SENTINEL_FUNC not in log_text
    assert "SECRET_IMPL" not in log_text

    # The returned and written file hold no gen/ content.
    file_value = field(result, "file")
    assert file_value is not None
    content = field(file_value, "content")
    assert GEN_SENTINEL not in content
    assert GEN_SENTINEL_FUNC not in content
    written = repo_root / field(file_value, "path")
    assert written.is_file()
    written_text = written.read_text(encoding="utf-8")
    assert GEN_SENTINEL not in written_text
    assert GEN_SENTINEL_FUNC not in written_text