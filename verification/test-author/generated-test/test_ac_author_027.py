# hotdocs-criterion: sha256:7899da96bf822ee97daf5691bc3aefde571e89462e8e9bc986a5c98690053cf4
import re
from pathlib import Path

import test_author


FINDING = {
    "kind": "undefined_name",
    "severity": "error",
    "line": 3,
    "message": "undefined name 'x'",
}

NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


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
        "criterion_text": "Given a widget When made Then it exists",
        "requirement_text": "R-WIDGET-MAKER-001 widgets MUST be made.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def plant_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "class ProbeReport:\n"
        "    def __init__(self, ok, findings, tests_run, tests_reached):\n"
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
        "GATE_VERSION = 'test-probe@1.5.0'\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None, drivers=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write(repr(test_source) + '\\n')\n"
        "    if test_source == " + repr("GOOD") + ":\n"
        "        return ProbeReport(True, [], 1, 1)\n"
        "    return ProbeReport(False, [dict(" + repr(FINDING) + ")], 0, 0)\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_backend(replies, prompts):
    queue = list(replies)

    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = NONCE_RE.findall(prompt)[-1]
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


def verification_files(repo_root):
    vdir = repo_root / "verification"
    if not vdir.exists():
        return []
    return [p for p in vdir.rglob("*") if p.is_file()]


def test_repair_succeeds_on_second_repair(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_calls.log"
    plant_probe_stand_in(repo_root, log_path)

    prompts = []
    backend = make_backend(["BAD1", "BAD2", "GOOD"], prompts)

    result = test_author.author_test(
        make_bundle(), "mock", 0, repo_root=repo_root, llm_backend=backend
    )

    assert len(prompts) == 3
    assert "BAD1" in prompts[1]
    assert "undefined_name (line 3): undefined name 'x'" in prompts[1]

    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").strip() != ""

    assert field(result, "model_call_error") is None
    assert field(result, "repair_attempts") == 2
    assert list(field(result, "probe_findings")) == []

    file_value = field(result, "file")
    assert file_value is not None
    content = field(file_value, "content")
    assert body(content) == "GOOD"

    written = repo_root / field(file_value, "path")
    assert written.is_file()
    written_text = written.read_text(encoding="utf-8")
    first, sep, rest = written_text.partition("\n")
    assert sep == "\n"
    assert rest == "GOOD"
    assert written_text == content


def test_repair_exhausted_reports_test_probe_failed(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_calls.log"
    plant_probe_stand_in(repo_root, log_path)

    prompts = []
    backend = make_backend(["BAD1", "BAD2", "BAD3"], prompts)

    result = test_author.author_test(
        make_bundle(), "mock", 0, repo_root=repo_root, llm_backend=backend
    )

    assert len(prompts) == 3

    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8").strip() != ""

    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "test_probe_failed"
    assert field(result, "file") is None
    assert field(result, "repair_attempts") == 2
    assert [dict(f) for f in field(result, "probe_findings")] == [FINDING]

    assert verification_files(repo_root) == []