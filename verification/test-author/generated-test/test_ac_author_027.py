# hotdocs-criterion: sha256:fb12eeaf210577cdc82c93f4076a4b8b6cc0a6ec42a5b8b264f5ed80d791ef66
import re
from pathlib import Path

import test_author


FINDING = {
    "kind": "undefined_name",
    "severity": "error",
    "line": 3,
    "message": "undefined name 'x'",
}

BUNDLE = {
    "component_id": "comp-widget-maker",
    "criterion_id": "AC-WIDGET-MAKER-001",
    "covers": "R-WIDGET-MAKER-001",
    "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
    "requirement_text": "R-WIDGET-MAKER-001 - make_widget MUST return a widget.",
    "interface": "make_widget() -> dict",
    "glossary": "",
    "dependency_interfaces": {},
}

NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def write_probe_stand_in(repo_root, log_path):
    source = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "FINDING = " + repr(FINDING) + "\n"
        "\n"
        "\n"
        "class _Report:\n"
        "    def __init__(self, ok, findings):\n"
        "        self.ok = ok\n"
        "        self.findings = findings\n"
        "        self.tests_run = 1 if ok else 0\n"
        "        self.tests_reached = 1 if ok else 0\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': [dict(f) for f in self.findings],\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None, drivers=None, **kwargs):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(test_source) + '\\n')\n"
        "    if test_source == 'GOOD':\n"
        "        return _Report(True, [])\n"
        "    return _Report(False, [dict(FINDING)])\n"
    )
    target = repo_root / "gen" / "test-probe" / "test_probe.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")


def make_backend(replies, prompts):
    queue = list(replies)

    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(NONCE_RE, prompt)[-1]
        file_text = queue.pop(0)
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + file_text
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def read_probe_log(log_path):
    import json

    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line]


def files_under_verification(repo_root):
    root = repo_root / "verification"
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file()]


def test_repairs_until_good_test_is_accepted(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, log_path)

    prompts = []
    backend = make_backend(["BAD1", "BAD2", "GOOD"], prompts)

    result = test_author.author_test(
        dict(BUNDLE), "mock", 0, repo_root=repo_root, llm_backend=backend
    )

    assert len(prompts) == 3
    assert "BAD1" in prompts[1]
    assert "undefined_name (line 3): undefined name 'x'" in prompts[1]

    assert read_probe_log(log_path) == ["BAD1", "BAD2", "GOOD"]

    assert field(result, "model_call_error") is None
    assert field(result, "repair_attempts") == 2
    assert list(field(result, "probe_findings")) == []

    file = field(result, "file")
    assert file is not None
    path = field(file, "path")
    written = repo_root / path
    assert written.is_file()
    content = written.read_text(encoding="utf-8")
    first, _, rest = content.partition("\n")
    assert first.startswith("# hotdocs-criterion:")
    assert rest == "GOOD"
    assert body(field(file, "content")) == "GOOD"


def test_all_repairs_fail_gives_test_probe_failed(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, log_path)

    prompts = []
    backend = make_backend(["BAD1", "BAD2", "BAD3"], prompts)

    result = test_author.author_test(
        dict(BUNDLE), "mock", 0, repo_root=repo_root, llm_backend=backend
    )

    assert len(prompts) == 3

    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "test_probe_failed"
    assert field(result, "file") is None
    assert field(result, "repair_attempts") == 2
    assert [dict(f) for f in field(result, "probe_findings")] == [FINDING]

    assert files_under_verification(repo_root) == []