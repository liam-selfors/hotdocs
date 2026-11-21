# hotdocs-criterion: sha256:eadfb3be65c24ab6b2f3b0742c39c41d2bb0cc08df4a90d55f76f4cc264319f7
import re
from pathlib import Path

import test_author


FINDING = {
    "kind": "undefined_name",
    "severity": "error",
    "line": 3,
    "message": "undefined name 'x'",
}

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
        "requirement_text": "R-WIDGET-MAKER-001 - a widget MUST be made.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "class _Report:\n"
        "    def __init__(self, ok, findings):\n"
        "        self.ok = ok\n"
        "        self.findings = findings\n"
        "        self.tests_run = 0\n"
        "        self.tests_reached = 0\n"
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(repr(test_source) + '\\n')\n"
        "    if test_source == " + repr("GOOD") + ":\n"
        "        return _Report(True, [])\n"
        "    return _Report(False, [dict(" + repr(FINDING) + ")])\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_backend(replies, prompts):
    queue = list(replies)

    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(NONCE_RE, prompt)[-1]
        content = queue.pop(0)
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


def files_under(path):
    path = Path(path)
    if not path.exists():
        return []
    return [p for p in path.rglob("*") if p.is_file()]


def setup_env(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    log_path = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, log_path)
    return repo_root, log_path


def test_repair_succeeds_on_second_repair(tmp_path, monkeypatch):
    repo_root, log_path = setup_env(tmp_path, monkeypatch)
    prompts = []
    backend = make_backend(["BAD1", "BAD2", "GOOD"], prompts)

    result = test_author.author_test(
        make_bundle(), "mock", 0, repo_root=repo_root, llm_backend=backend
    )

    assert len(prompts) == 3
    assert "BAD1" in prompts[1]
    assert "undefined_name (line 3): undefined name 'x'" in prompts[1]

    assert field(result, "model_call_error") is None
    assert field(result, "repair_attempts") == 2
    assert list(field(result, "probe_findings")) == []

    file_info = field(result, "file")
    assert file_info is not None
    written = repo_root / file_info["path"]
    assert written.is_file()
    written_content = written.read_text(encoding="utf-8")
    assert written_content.partition("\n")[0].startswith("# hotdocs-criterion:")
    assert body(written_content) == "GOOD"
    assert body(file_info["content"]) == "GOOD"

    # The stand-in probe actually ran for each candidate.
    assert log_path.is_file()
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 3


def test_repair_exhausted_returns_probe_failure(tmp_path, monkeypatch):
    repo_root, log_path = setup_env(tmp_path, monkeypatch)
    prompts = []
    backend = make_backend(["BAD1", "BAD2", "BAD3"], prompts)

    result = test_author.author_test(
        make_bundle(), "mock", 0, repo_root=repo_root, llm_backend=backend
    )

    assert len(prompts) == 3

    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "test_probe_failed"
    assert field(result, "file") is None
    assert field(result, "repair_attempts") == 2
    assert [dict(f) for f in field(result, "probe_findings")] == [FINDING]

    assert files_under(repo_root / "verification") == []
    assert files_under(repo_root / ".hotdocs" / "cache") == []

    assert log_path.is_file()
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 3