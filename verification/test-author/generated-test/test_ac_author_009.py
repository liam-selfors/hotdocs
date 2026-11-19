# hotdocs-criterion: sha256:357cd8450846c100bc760204a36987d478df48cfb7aaba4ce09f73202a1c0760
import re
from pathlib import Path

import test_author


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

TEST_CODE = (
    "import os\n"
    "\n"
    "\n"
    "def test_widget_sep():\n"
    "    assert os.sep"
)


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
        "requirement_text": "R-WIDGET-MAKER-001 The maker MUST make widgets.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }


def write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    src = (
        "import dataclasses\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "GATE_VERSION = 'test-probe@1.3.0'\n"
        "\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class ProbeReport:\n"
        "    ok: bool\n"
        "    findings: list\n"
        "    tests_run: int\n"
        "    tests_reached: int\n"
        "\n"
        "    def to_dict(self):\n"
        "        return dataclasses.asdict(self)\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(repr(test_source) + '\\n')\n"
        "    return ProbeReport(ok=True, findings=[], tests_run=1, tests_reached=1)\n"
    )
    (probe_dir / "test_probe.py").write_text(src)


def setup_repo(tmp_path, monkeypatch, name):
    repo_root = tmp_path / name
    repo_root.mkdir()
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / (name + "-probe.log")
    write_probe_stand_in(repo_root, log_path)
    return repo_root, log_path


def cache_entries(repo_root):
    cache_dir = repo_root / ".hotdocs" / "cache"
    if not cache_dir.exists():
        return []
    return [p for p in cache_dir.rglob("*") if p.is_file()]


def verification_files(repo_root):
    vdir = repo_root / "verification"
    if not vdir.exists():
        return []
    return [p for p in vdir.rglob("*") if p.is_file()]


def test_extracts_strictly_between_markers_ignoring_fence_and_narration(tmp_path, monkeypatch):
    repo_root, log_path = setup_repo(tmp_path, monkeypatch, "repo_wrapped")

    def backend(prompt, model, **params):
        n = re.findall(NONCE_RE, prompt)[-1]
        text = (
            "Sure, here is the test file you asked for.\n"
            "```python\n"
            "-----BEGIN FILE " + n + "-----\n"
            + TEST_CODE
            + "\n-----END FILE " + n + "-----\n"
            "```\n"
            "Let me know if you need anything else."
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
    assert "```" not in content
    assert "BEGIN FILE" not in content
    assert "END FILE" not in content
    assert "Sure, here is" not in content
    assert "Let me know" not in content

    written = repo_root / file["path"]
    assert written.is_file()
    assert body(written.read_text()) == TEST_CODE


def test_no_marker_pair_is_distinct_failure_and_writes_nothing(tmp_path, monkeypatch):
    repo_root, log_path = setup_repo(tmp_path, monkeypatch, "repo_nomarkers")

    def backend(prompt, model, **params):
        text = (
            "Here is the test:\n"
            "```python\n"
            + TEST_CODE
            + "\n```\n"
            "Done."
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
    assert cache_entries(repo_root) == []
    assert verification_files(repo_root) == []
    assert not (repo_root / "verification" / "widget-maker" / "generated-test").exists()