# hotdocs-criterion: sha256:e374399d1ff8ad6ca424d5ccd60f36f2437c31e7d6809c0cfc703c69a01c5b56
import re
from pathlib import Path

import test_author


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 widgets MUST be made.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def plant_probe(repo_root, log_path):
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
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(repr(test_source) + '\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def verification_files(repo_root):
    root = repo_root / "verification"
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file()]


def test_extracts_only_text_between_markers(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_calls.log"
    plant_probe(repo_root, log_path)

    code = "import os\n\n\ndef test_widget():\n    assert os.sep"
    narration_before = "Here is the test file you asked for:"
    narration_after = "Let me know if you need anything else."
    replies = []

    def backend(prompt, model, **params):
        nonce = re.findall(NONCE_RE, prompt)[-1]
        text = (
            narration_before + "\n"
            + "```python\n"
            + "-----BEGIN FILE " + nonce + "-----\n"
            + code + "\n"
            + "-----END FILE " + nonce + "-----\n"
            + "```\n"
            + narration_after + "\n"
        )
        replies.append(text)
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    result = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root, llm_backend=backend
    )

    assert replies, "mock model was never called"
    assert field(result, "model_call_error") is None
    file = field(result, "file")
    assert file is not None
    content = field(file, "content")

    assert body(content) == code
    assert "```" not in content
    assert narration_before not in content
    assert narration_after not in content
    assert "-----BEGIN FILE" not in content
    assert "-----END FILE" not in content

    written = repo_root / field(file, "path")
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == content


def test_reply_without_markers_is_rejected(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_calls.log"
    plant_probe(repo_root, log_path)

    reply = "Sure! ```python\nimport os\n\ndef test_widget():\n    assert os.sep\n```\n"
    calls = []

    def backend(prompt, model, **params):
        calls.append(prompt)
        return {"text": reply, "model": model, "backend": "mock", "model_call_error": None}

    result = test_author.author_test(
        make_bundle(), "mock", repo_root=repo_root, llm_backend=backend
    )

    assert calls, "mock model was never called"
    assert field(result, "file") is None
    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "missing_file_markers"
    expected_message = (
        "model reply held no matching BEGIN/END FILE markers; reply began: "
        + repr(reply[:200])
    )
    assert field(error, "message") == expected_message

    assert verification_files(repo_root) == []
    assert not (repo_root / "verification" / "widget-maker" / "generated-test").exists() or not any(
        (repo_root / "verification" / "widget-maker" / "generated-test").iterdir()
    )