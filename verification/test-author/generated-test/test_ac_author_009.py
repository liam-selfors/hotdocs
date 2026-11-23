# hotdocs-criterion: sha256:fa097113b234380ec8a8ebcf2816b858b9e6e6d067a36c00b05fdd0e1c8f6e9f
import json
import re
from pathlib import Path

import test_author


MARKER_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

REAL_CODE = (
    "import os\n"
    "\n"
    "\n"
    "def test_something():\n"
    "    assert os.sep\n"
)

NARRATION_BEFORE = "Sure! Here is the test file you asked for:"
NARRATION_AFTER = "Let me know if you need any changes."


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
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - make_widget MUST return a widget.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def setup_repo(repo_root, monkeypatch):
    repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    probe_log = repo_root / "probe_calls.log"
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(probe_log)) + "\n"
        "GATE_VERSION = " + repr("test-probe@1.4.0") + "\n"
        "\n"
        "\n"
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps(test_source) + '\\n')\n"
        "    return ProbeReport()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")
    return probe_log


def read_probe_calls(probe_log):
    if not probe_log.exists():
        return []
    return [
        json.loads(line)
        for line in probe_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def files_under(path):
    if not path.exists():
        return []
    return [p for p in path.rglob("*") if p.is_file()]


def test_extracts_only_text_between_markers(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo_fenced"
    probe_log = setup_repo(repo_root, monkeypatch)

    def backend(prompt, model, **params):
        nonce = re.findall(MARKER_RE, prompt)[-1]
        text = (
            NARRATION_BEFORE + "\n"
            "```python\n"
            "-----BEGIN FILE " + nonce + "-----\n"
            + REAL_CODE
            + "\n-----END FILE " + nonce + "-----\n"
            "```\n"
            + NARRATION_AFTER + "\n"
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
    content = field(file, "content")

    assert body(content) == REAL_CODE
    assert "```" not in content
    assert "BEGIN FILE" not in content
    assert "END FILE" not in content
    assert NARRATION_BEFORE not in content
    assert NARRATION_AFTER not in content

    # The probe saw exactly the extracted text.
    calls = read_probe_calls(probe_log)
    assert calls, "test-probe stand-in was never called"
    assert calls[-1] == REAL_CODE

    # The written file holds the same content.
    rel_path = field(file, "path")
    assert rel_path == "verification/widget-maker/generated-test/test_ac_widget_maker_001.py"
    written = (repo_root / rel_path).read_text(encoding="utf-8")
    assert written == content
    assert body(written) == REAL_CODE


def test_no_marker_pair_is_authoring_failure(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo_nomarkers"
    setup_repo(repo_root, monkeypatch)

    def backend(prompt, model, **params):
        text = (
            NARRATION_BEFORE + "\n"
            "```python\n"
            + REAL_CODE
            + "```\n"
            + NARRATION_AFTER + "\n"
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
    assert field(result, "cache_hit") is False

    assert files_under(repo_root / "verification") == []
    assert files_under(repo_root / ".hotdocs" / "cache") == []