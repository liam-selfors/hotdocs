# hotdocs-criterion: sha256:dbb74f975dc115a366eff892074a3bb5bb5c5c7f6ed735a9426fe659ab58170d
import json
import re

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
        "requirement_text": "R-WIDGET-MAKER-001 - make_widget MUST return a widget.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def plant_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
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
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(test_source) + '\\n')\n"
        "    if test_source == 'GOOD':\n"
        "        return _Report(True, [])\n"
        "    return _Report(False, [dict(FINDING)])\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def read_probe_log(log_path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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


def nothing_under_verification(repo_root):
    verification = repo_root / "verification"
    if not verification.exists():
        return True
    return not any(p.is_file() for p in verification.rglob("*"))


def test_repair_succeeds_on_second_repair(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "probe_calls.log"
    plant_probe_stand_in(repo_root, log_path)
    monkeypatch.chdir(repo_root)

    prompts = []
    backend = make_backend(["BAD1", "BAD2", "GOOD"], prompts)

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
    assert field(result, "probe_findings") == []

    file = field(result, "file")
    assert file is not None
    path = field(file, "path")
    content = field(file, "content")
    assert body(content) == "GOOD"

    written = repo_root / path
    assert written.is_file()
    written_text = written.read_bytes().decode("utf-8")
    first_line, sep, rest = written_text.partition("\n")
    assert sep == "\n"
    assert first_line.startswith("# hotdocs-criterion:")
    assert rest == "GOOD"
    assert written_text == content


def test_repair_exhausted_gives_test_probe_failed(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "probe_calls.log"
    plant_probe_stand_in(repo_root, log_path)
    monkeypatch.chdir(repo_root)

    prompts = []
    backend = make_backend(["BAD1", "BAD2", "BAD3"], prompts)

    result = test_author.author_test(
        make_bundle(), "mock", 0, repo_root=repo_root, llm_backend=backend
    )

    assert len(prompts) == 3
    assert read_probe_log(log_path) == ["BAD1", "BAD2", "BAD3"]

    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "test_probe_failed"
    assert field(result, "file") is None
    assert field(result, "repair_attempts") == 2
    assert field(result, "probe_findings") == [FINDING]

    assert nothing_under_verification(repo_root)