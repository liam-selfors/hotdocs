# hotdocs-criterion: sha256:3f766f3de3ba30aac3fe64f8e3c106cb8b0d3f5d6f8be2ee02f790e8a9511205
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


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


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget, When made, Then it exists.",
        "requirement_text": "R-WIDGET-MAKER-001 -- make_widget MUST return a widget.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_deleted_test_is_authored_afresh_never_restored(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    calls = []
    contents = ["import x", "import y"]

    def mock_backend(prompt, model, **params):
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        index = len(calls)
        calls.append(prompt)
        file_text = contents[index] if index < len(contents) else contents[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + file_text + "\n"
            + "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = _bundle()

    first = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=mock_backend
    )
    assert field(first, "model_call_error") is None
    first_file = field(first, "file")
    assert first_file is not None
    written = repo_root / first_file["path"]
    assert written.is_file()
    assert body(first_file["content"]) == "import x"

    written.unlink()
    assert not written.exists()

    second = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=mock_backend
    )
    assert field(second, "model_call_error") is None

    assert len(calls) == 2

    assert field(first, "cache_hit") is False
    assert field(second, "cache_hit") is False

    second_file = field(second, "file")
    assert second_file is not None
    second_content = second_file["content"]
    first_line, _, rest = second_content.partition("\n")
    assert first_line.startswith("# hotdocs-criterion:")
    assert rest == "import y"
    assert body(second_content) == "import y"

    assert not (repo_root / ".hotdocs" / "cache").exists()