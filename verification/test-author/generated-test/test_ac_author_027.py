# hotdocs-criterion: sha256:1171a5524b9d42c5082e74b4b9e55c756ed29f487d58a847a93cb71d22318e66
import json
import re

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
        "requirement_text": "R-WIDGET-MAKER-001 - make_widget MUST return a widget.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def write_probe_stand_in(repo_root, log_path):
    target = repo_root / "gen" / "test-probe" / "test_probe.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "FINDING = " + repr(FINDING) + "\n"
        "GATE_VERSION = 'test-probe@1.4.0'\n"
        "\n"
        "\n"
        "class ProbeReport:\n"
        "    def __init__(self, ok, findings, tests_run=0, tests_reached=0):\n"
        "        self.ok = ok\n"
        "        self.findings = findings\n"
        "        self.tests_run = tests_run\n"
        "        self.tests_reached = tests_reached\n"
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
        "          interpreter=None, assets=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(test_source) + '\\n')\n"
        "    if test_source == 'GOOD':\n"
        "        return ProbeReport(True, [], 1, 1)\n"
        "    return ProbeReport(False, [dict(FINDING)], 0, 0)\n"
    )
    target.write_text(source, encoding="utf-8")


def make_mock(replies, prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(NONCE_RE, prompt)[-1]
        reply = replies[min(len(prompts) - 1, len(replies) - 1)]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + reply
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
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def written_files(repo_root):
    verification = repo_root / "verification"
    if not verification.exists():
        return []
    return [p for p in verification.rglob("*") if p.is_file()]


def test_repair_succeeds_on_second_repair(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, log_path)
    monkeypatch.chdir(repo_root)

    prompts = []
    backend = make_mock(["BAD1", "BAD2", "GOOD"], prompts)

    result = test_author.author_test(
        make_bundle(), "mock", 0, repo_root=repo_root, llm_backend=backend
    )

    assert len(prompts) == 3
    second = prompts[1]
    assert "BAD1" in second
    assert "undefined_name (line 3): undefined name 'x'" in second

    assert read_probe_log(log_path) == ["BAD1", "BAD2", "GOOD"]

    assert field(result, "model_call_error") is None
    assert field(result, "repair_attempts") == 2
    assert list(field(result, "probe_findings")) == []

    file = field(result, "file")
    assert file is not None
    content = field(file, "content")
    assert body(content) == "GOOD"

    written = repo_root / field(file, "path")
    assert written.is_file()
    assert body(written.read_text(encoding="utf-8")) == "GOOD"


def test_repair_exhausted_reports_probe_failure(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, log_path)
    monkeypatch.chdir(repo_root)

    prompts = []
    backend = make_mock(["BAD1", "BAD2", "BAD3"], prompts)

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

    assert written_files(repo_root) == []