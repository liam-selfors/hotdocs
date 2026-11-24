# hotdocs-criterion: sha256:4de78ab9a4f03d5ca65e14479706c45a07db70672db5f2c7273432550bd82c4b
import re
from pathlib import Path

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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None, assets=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def _make_mock(log_path):
    contents = ["import x", "import y"]

    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        calls = len(log_path.read_text(encoding="utf-8").splitlines())
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        content = contents[min(calls, len(contents)) - 1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + content
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_ac_author_030_deleted_test_is_authored_afresh(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = logs / "probe.log"
    model_log = logs / "model.log"
    _write_probe_stand_in(repo_root, probe_log)
    mock = _make_mock(model_log)

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 widgets MUST be makeable.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }

    first = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=mock
    )
    first_file = field(first, "file")
    assert first_file is not None
    written = repo_root / first_file["path"]
    assert written.is_file()
    written.unlink()
    assert not written.exists()

    second = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=mock
    )

    assert len(model_log.read_text(encoding="utf-8").splitlines()) == 2
    assert field(first, "cache_hit") is False
    assert field(second, "cache_hit") is False

    second_file = field(second, "file")
    assert second_file is not None
    assert body(second_file["content"]) == "import y"

    assert not (repo_root / ".hotdocs" / "cache").exists()