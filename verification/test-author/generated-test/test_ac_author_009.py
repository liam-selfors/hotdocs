# hotdocs-criterion: sha256:49d2a44618a43be310823f40b9f76051c8b5216c24af9f25ad3b19240ef81544
import json
import re
from pathlib import Path

import test_author


BEGIN_PREFIX = "-----BEGIN " + "FILE "
END_PREFIX = "-----END " + "FILE "
MARK_SUFFIX = "-----"
NONCE_RE = re.compile(re.escape(BEGIN_PREFIX) + "([0-9a-f]{32})" + re.escape(MARK_SUFFIX))


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


def plant_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "import json",
        "",
        "LOG = " + repr(str(log_path)),
        "",
        "",
        "class ProbeReport:",
        "    def __init__(self):",
        "        self.ok = True",
        "        self.findings = []",
        "        self.tests_run = 1",
        "        self.tests_reached = 1",
        "",
        "    def to_dict(self):",
        "        return {",
        "            'ok': self.ok,",
        "            'findings': list(self.findings),",
        "            'tests_run': self.tests_run,",
        "            'tests_reached': self.tests_reached,",
        "        }",
        "",
        "",
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,",
        "          interpreter=None, assets=None, drivers=None, **kwargs):",
        "    with open(LOG, 'a', encoding='utf-8') as fh:",
        "        fh.write(json.dumps({'test_source': test_source}) + '\\n')",
        "    return ProbeReport()",
        "",
    ]
    (probe_dir / "test_probe.py").write_text("\n".join(lines), encoding="utf-8")


def read_log(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def make_backend(reply_for_nonce, call_log):
    def backend(prompt, model, **params):
        nonce = NONCE_RE.findall(prompt)[-1]
        with open(call_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"nonce": nonce}) + "\n")
        return {
            "text": reply_for_nonce(nonce),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def files_under(path):
    if not path.exists():
        return []
    return [p for p in path.rglob("*") if p.is_file()]


def test_extracts_exactly_between_markers_discarding_fence_and_narration(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo_extract"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    probe_log = tmp_path / "probe_extract.log"
    call_log = tmp_path / "calls_extract.log"
    plant_probe_stand_in(repo_root, probe_log)

    code = (
        "import os\n"
        "\n"
        "\n"
        "def test_sep():\n"
        "    assert os.sep\n"
    )
    narration_before = "Sure! Here is the complete test file you asked for."
    narration_after = "Let me know if you need anything else."

    def reply(nonce):
        return (
            narration_before + "\n"
            + "```python\n"
            + BEGIN_PREFIX + nonce + MARK_SUFFIX + "\n"
            + code + "\n"
            + END_PREFIX + nonce + MARK_SUFFIX + "\n"
            + "```\n"
            + narration_after + "\n"
        )

    result = test_author.author_test(
        make_bundle(), "mock", 0, repo_root=repo_root,
        llm_backend=make_backend(reply, call_log),
    )

    assert len(read_log(call_log)) >= 1
    assert field(result, "model_call_error") is None
    file = field(result, "file")
    assert file is not None
    content = field(file, "content")

    assert body(content) == code
    assert "```" not in content
    assert narration_before not in content
    assert narration_after not in content
    assert BEGIN_PREFIX not in content
    assert END_PREFIX not in content

    probe_calls = read_log(probe_log)
    assert len(probe_calls) >= 1
    assert probe_calls[-1]["test_source"] == code

    path = field(file, "path")
    assert path == "verification/widget-maker/generated-test/test_ac_widget_maker_001.py"
    written = repo_root / path
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == content


def test_reply_without_markers_is_distinct_failure_and_writes_nothing(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo_nomarkers"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    probe_log = tmp_path / "probe_nomarkers.log"
    call_log = tmp_path / "calls_nomarkers.log"
    plant_probe_stand_in(repo_root, probe_log)

    no_marker_reply = (
        "Here is the test:\n"
        "```python\n"
        "import os\n"
        "\n"
        "\n"
        "def test_sep():\n"
        "    assert os.sep\n"
        "```\n"
        "Hope that helps.\n"
    )

    def reply(nonce):
        return no_marker_reply

    result = test_author.author_test(
        make_bundle(), "mock", 0, repo_root=repo_root,
        llm_backend=make_backend(reply, call_log),
    )

    assert len(read_log(call_log)) >= 1
    assert field(result, "file") is None

    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "missing_file_markers"
    assert field(error, "message") == (
        "model reply held no matching BEGIN/END FILE markers; reply began: "
        + repr(no_marker_reply[:200])
    )

    assert files_under(repo_root / "verification") == []
    assert files_under(repo_root / "verification" / "widget-maker" / "generated-test") == []