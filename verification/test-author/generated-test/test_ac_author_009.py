# hotdocs-criterion: sha256:5575671abe1a3152afdb8c2c1fdeb7113ede8e9c473f481d3c696a02ead0208f
import json
import re
from pathlib import Path

import test_author


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

REAL_TEST_CODE = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_widget():\n"
    "    assert widget_maker.make() == 1"
)

NARRATION_BEFORE = "Sure! Here is the complete test file you asked for:"
NARRATION_AFTER = "Let me know if you want any changes."


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
        "criterion_text": "Given a widget, when made, then it is 1.",
        "requirement_text": "R-WIDGET-MAKER-001 - make() MUST return 1.",
        "interface": "make() -> int",
        "glossary": "",
        "dependency_interfaces": {},
    }


def plant_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = "\n".join([
        "import json",
        "",
        "GATE_VERSION = 'test-probe@1.5.0'",
        "",
        "",
        "class _Report:",
        "    def __init__(self):",
        "        self.ok = True",
        "        self.findings = []",
        "        self.tests_run = 1",
        "        self.tests_reached = 1",
        "",
        "    def to_dict(self):",
        "        return {'ok': True, 'findings': [], 'tests_run': 1, 'tests_reached': 1}",
        "",
        "",
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,"
        " interpreter=None, assets=None, drivers=None):",
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:",
        "        fh.write(json.dumps(test_source) + '\\n')",
        "    return _Report()",
        "",
    ])
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def read_probe_calls(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line]


def files_under_verification(repo_root):
    verification = repo_root / "verification"
    if not verification.exists():
        return []
    return [p for p in verification.rglob("*") if p.is_file()]


def test_extracts_exactly_between_markers_discarding_fence_and_narration(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_calls.log"
    plant_probe_stand_in(repo_root, log_path)

    def mock_backend(prompt, model, **params):
        nonces = re.findall(NONCE_RE, prompt)
        assert nonces, "prompt carries no BEGIN FILE nonce marker"
        n = nonces[-1]
        text = (
            NARRATION_BEFORE + "\n"
            + "```python\n"
            + "-----BEGIN FILE " + n + "-----\n"
            + REAL_TEST_CODE + "\n"
            + "-----END FILE " + n + "-----\n"
            + "```\n"
            + NARRATION_AFTER
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    result = test_author.author_test(
        make_bundle(), "mock", 0, repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "model_call_error") is None
    file = field(result, "file")
    assert file is not None
    content = file["content"]

    assert body(content) == REAL_TEST_CODE
    assert "```" not in content
    assert NARRATION_BEFORE not in content
    assert NARRATION_AFTER not in content
    assert "-----BEGIN FILE" not in content
    assert "-----END FILE" not in content

    calls = read_probe_calls(log_path)
    assert calls, "test-probe stand-in was never called"
    assert calls[-1] == REAL_TEST_CODE

    assert file["path"] == "verification/widget-maker/generated-test/test_ac_widget_maker_001.py"
    written = repo_root / file["path"]
    assert written.is_file()
    written_text = written.read_text(encoding="utf-8")
    assert written_text == content
    assert body(written_text) == REAL_TEST_CODE


def test_no_marker_pair_is_authoring_failure_and_writes_nothing(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_calls.log"
    plant_probe_stand_in(repo_root, log_path)

    def mock_backend(prompt, model, **params):
        text = (
            NARRATION_BEFORE + "\n"
            + "```python\n"
            + REAL_TEST_CODE + "\n"
            + "```\n"
            + NARRATION_AFTER
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    result = test_author.author_test(
        make_bundle(), "mock", 0, repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "file") is None
    assert files_under_verification(repo_root) == []
    assert not (repo_root / "verification" / "widget-maker" / "generated-test").exists() or not any(
        (repo_root / "verification" / "widget-maker" / "generated-test").iterdir()
    )