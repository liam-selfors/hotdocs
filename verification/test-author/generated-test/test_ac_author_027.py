# hotdocs-criterion: sha256:b7195c65721999905acf232e377ade7ba98bc398fa50ed3b4e64b2c7ba05be31
import json
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
        "criterion_text": "Given a widget When made Then it exists",
        "requirement_text": "R-WIDGET-MAKER-001 widgets MUST be made.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def plant_probe(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "import json",
        "",
        "LOG = " + repr(str(log_path)),
        "FINDING = " + repr(FINDING),
        "",
        "",
        "class ProbeReport:",
        "    def __init__(self, ok, findings):",
        "        self.ok = ok",
        "        self.findings = findings",
        "        self.tests_run = 1 if ok else 0",
        "        self.tests_reached = 1 if ok else 0",
        "",
        "    def to_dict(self):",
        "        return {",
        "            'ok': self.ok,",
        "            'findings': [dict(f) for f in self.findings],",
        "            'tests_run': self.tests_run,",
        "            'tests_reached': self.tests_reached,",
        "        }",
        "",
        "",
        "def probe(test_source, criterion_bundle, module_name, **kwargs):",
        "    with open(LOG, 'a', encoding='utf-8') as fh:",
        "        fh.write(json.dumps(test_source) + '\\n')",
        "    if test_source == 'GOOD':",
        "        return ProbeReport(True, [])",
        "    return ProbeReport(False, [dict(FINDING)])",
        "",
    ]
    (probe_dir / "test_probe.py").write_text("\n".join(lines), encoding="utf-8")


def make_backend(replies, prompts):
    queue = list(replies)

    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(NONCE_RE, prompt)[-1]
        reply = queue.pop(0)
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


def verification_files(repo_root):
    vdir = repo_root / "verification"
    if not vdir.exists():
        return []
    return [p for p in vdir.rglob("*") if p.is_file()]


def test_repair_succeeds_on_second_repair(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo1"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe1.log"
    plant_probe(repo_root, log_path)

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
    assert field(result, "probe_findings") == []

    file = field(result, "file")
    assert file is not None
    assert body(field(file, "content")) == "GOOD"

    written = repo_root / field(file, "path")
    assert written.is_file()
    written_content = written.read_text(encoding="utf-8")
    assert body(written_content) == "GOOD"
    assert written_content.partition("\n")[0].startswith("# hotdocs-criterion:")

    probed = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert probed == ["BAD1", "BAD2", "GOOD"]


def test_repair_exhausted_reports_test_probe_failed(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo2"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe2.log"
    plant_probe(repo_root, log_path)

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
    assert field(result, "probe_findings") == [FINDING]

    assert verification_files(repo_root) == []