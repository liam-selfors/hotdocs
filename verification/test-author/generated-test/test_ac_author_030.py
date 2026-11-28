# hotdocs-criterion: sha256:9f0e75c2beaf437d4421936a38523649b2b4bbe9a627da209fe6f89b99d096cc
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
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            " + repr("ok") + ": self.ok,\n"
        "            " + repr("findings") + ": [dict(f) for f in self.findings],\n"
        "            " + repr("tests_run") + ": self.tests_run,\n"
        "            " + repr("tests_reached") + ": self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(LOG_PATH, " + repr("a") + ", encoding=" + repr("utf-8") + ") as f:\n"
        "        f.write(json.dumps(test_source) + " + repr("\n") + ")\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget, When it is made, Then it exists.",
        "requirement_text": "R-WIDGET-MAKER-001 - make_widget MUST return a widget.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_deleted_test_is_authored_afresh_with_no_cache(tmp_path, monkeypatch):
    repo_root = tmp_path
    monkeypatch.chdir(repo_root)

    probe_log = repo_root / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    calls = []
    contents = ["import x", "import y"]

    def mock_backend(prompt, model, **params):
        calls.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        index = min(len(calls) - 1, len(contents) - 1)
        reply = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + contents[index]
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": reply,
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
    assert body(second_file["content"]) == "import y"

    assert not (repo_root / ".hotdocs" / "cache").exists()