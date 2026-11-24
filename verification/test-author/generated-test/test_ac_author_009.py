# hotdocs-criterion: sha256:fd3a7afed9865df57208b3d9a971c8f63b112c74ddace2a884a57053ad0b3e4f
import json
import re
from pathlib import Path

import test_author


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

TEST_CODE = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_make_returns_one():\n"
    "    assert widget_maker.make() == 1\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-009",
        "covers": "R-WIDGET-MAKER-009",
        "criterion_text": "Given a widget\nWhen make is called\nThen it returns 1",
        "requirement_text": "R-WIDGET-MAKER-009 make MUST return 1.",
        "interface": "make() -> int",
        "glossary": "",
        "dependency_interfaces": {},
        "module_names": ["widget_maker"],
    }


def plant_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "GATE_VERSION = " + repr("test-probe@1.4.0") + "\n"
        "\n"
        "\n"
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'test_source': test_source}) + '\\n')\n"
        "    return ProbeReport(True, [], 1, 1)\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def read_probe_calls(log_path):
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def files_under_verification(repo_root):
    verification = repo_root / "verification"
    if not verification.exists():
        return []
    return [p for p in verification.rglob("*") if p.is_file()]


def test_extracts_strictly_between_markers_discarding_fence_and_narration(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_calls.log"
    plant_probe_stand_in(repo_root, log_path)

    narration_before = "Sure! Here is the requested test file for you."
    narration_after = "Let me know if you need any changes to this test."

    def backend(prompt, model, **params):
        nonce = re.findall(NONCE_RE, prompt)[-1]
        text = (
            narration_before + "\n"
            + "```python\n"
            + "-----BEGIN FILE " + nonce + "-----\n"
            + TEST_CODE + "\n"
            + "-----END FILE " + nonce + "-----\n"
            + "```\n"
            + narration_after + "\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        make_bundle(), "mock", 0, repo_root=repo_root, llm_backend=backend
    )

    assert field(result, "model_call_error") is None
    file = field(result, "file")
    assert file is not None
    content = file["content"]
    extracted = body(content)

    assert extracted == TEST_CODE
    assert "```" not in extracted
    assert narration_before not in extracted
    assert narration_after not in extracted
    assert "-----BEGIN FILE" not in extracted
    assert "-----END FILE" not in extracted

    calls = read_probe_calls(log_path)
    assert len(calls) >= 1
    assert calls[-1]["test_source"] == TEST_CODE

    assert file["path"] == "verification/widget-maker/generated-test/test_ac_widget_maker_009.py"
    written = repo_root / file["path"]
    assert written.is_file()
    assert written.read_text(encoding="utf-8") == content
    assert body(written.read_text(encoding="utf-8")) == TEST_CODE


def test_reply_without_markers_is_authoring_failure_and_writes_nothing(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_calls.log"
    plant_probe_stand_in(repo_root, log_path)

    def backend(prompt, model, **params):
        text = (
            "Here is the test file:\n"
            + "```python\n"
            + TEST_CODE
            + "```\n"
            + "Hope this helps.\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        make_bundle(), "mock", 0, repo_root=repo_root, llm_backend=backend
    )

    assert field(result, "file") is None
    assert files_under_verification(repo_root) == []
    assert not (repo_root / "verification" / "widget-maker" / "generated-test").exists() or not any(
        (repo_root / "verification" / "widget-maker" / "generated-test").iterdir()
    )