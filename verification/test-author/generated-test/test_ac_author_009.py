# hotdocs-criterion: sha256:ef75ffc5a96ffdc188d18865208112021e28044be8538abb336bc9004dc7e02d
import json
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

REAL_CODE = (
    "import pytest\n"
    "\n"
    "\n"
    "def test_something():\n"
    "    assert 1 + 1 == 2"
)


def make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget When made Then it exists",
        "requirement_text": "R-WIDGET-MAKER-001 The maker MUST make widgets.",
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
        "",
        "",
        "class Report:",
        "    def __init__(self):",
        "        self.ok = True",
        "        self.findings = []",
        "        self.tests_run = 1",
        "        self.tests_reached = 1",
        "",
        "    def to_dict(self):",
        "        return dict(ok=self.ok, findings=list(self.findings),"
        " tests_run=self.tests_run, tests_reached=self.tests_reached)",
        "",
        "",
        "def probe(test_source, criterion_bundle, module_name, **kwargs):",
        "    with open(LOG, 'a', encoding='utf-8') as f:",
        "        f.write(json.dumps(test_source) + '\\n')",
        "    return Report()",
        "",
    ]
    (probe_dir / "test_probe.py").write_text("\n".join(lines), encoding="utf-8")


def files_under_verification(repo_root):
    root = repo_root / "verification"
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file()]


def test_extracts_strictly_between_markers(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo_a"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_a.log"
    plant_probe(repo_root, log_path)

    calls = []

    def backend(prompt, model, **params):
        calls.append(prompt)
        nonce = re.findall(NONCE_RE, prompt)[-1]
        text = (
            "Here is the test file you asked for:\n"
            "```python\n"
            "-----BEGIN FILE " + nonce + "-----\n"
            + REAL_CODE + "\n"
            "-----END FILE " + nonce + "-----\n"
            "```\n"
            "Let me know if you need anything else."
        )
        return {"text": text, "model": model, "backend": "mock",
                "model_call_error": None}

    result = test_author.author_test(
        make_bundle(), "mock", 0, repo_root=repo_root, llm_backend=backend
    )

    assert calls, "mock model was never called"
    assert field(result, "model_call_error") is None
    f = field(result, "file")
    assert f is not None
    content = field(f, "content")
    extracted = body(content)
    assert extracted == REAL_CODE
    assert "```" not in extracted
    assert "Here is the test file" not in extracted
    assert "Let me know" not in extracted
    assert "-----BEGIN FILE" not in content
    assert "-----END FILE" not in content

    written = repo_root / field(f, "path")
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == content

    probed = [json.loads(line) for line in
              log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert probed, "test-probe stand-in was never called"
    assert probed[-1] == REAL_CODE


def test_no_marker_pair_is_authoring_failure(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo_b"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_b.log"
    plant_probe(repo_root, log_path)

    calls = []

    def backend(prompt, model, **params):
        calls.append(prompt)
        text = (
            "Sure, here is the test:\n"
            "```python\n"
            + REAL_CODE + "\n"
            "```\n"
            "Done."
        )
        return {"text": text, "model": model, "backend": "mock",
                "model_call_error": None}

    result = test_author.author_test(
        make_bundle(), "mock", 0, repo_root=repo_root, llm_backend=backend
    )

    assert calls, "mock model was never called"
    assert field(result, "file") is None
    assert files_under_verification(repo_root) == []
    assert not (repo_root / "verification" / "widget-maker" / "generated-test").exists() or \
        list((repo_root / "verification" / "widget-maker" / "generated-test").iterdir()) == []