# hotdocs-criterion: sha256:57444f95e6b084da68721fdf1c7ab9ee4c6c58d50d52d573c345c0609743fbea
import json
import re

import test_author


TEST_CONTENT = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_make():\n"
    "    assert widget_maker.make() == 1\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "GATE_VERSION = " + repr("test-probe@1.3.0") + "\n"
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'test_source': test_source, 'module_name': module_name}) + '\\n')\n"
        "    findings = [{\n"
        "        'kind': 'undefined_name',\n"
        "        'severity': 'error',\n"
        "        'line': 1,\n"
        "        'message': \"undefined name 'tmp_dir'\",\n"
        "    }]\n"
        "    return ProbeReport(False, findings, 0, 0)\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def _mock_backend(prompt, model, **params):
    nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
    text = (
        "-----BEGIN FILE " + nonce + "-----\n"
        + TEST_CONTENT
        + "\n-----END FILE " + nonce + "-----"
    )
    return {
        "text": text,
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def test_ac_author_020_probe_rejects_and_nothing_written(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    log_path = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, log_path)

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget maker\nWhen make() is called\nThen it returns 1",
        "requirement_text": "R-WIDGET-MAKER-001 make() MUST return 1.",
        "interface": "make() -> int",
        "glossary": "",
        "dependency_interfaces": {},
    }

    test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=_mock_backend
    )

    assert log_path.is_file(), "test-probe stand-in was never called"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) >= 1
    first = json.loads(lines[0])
    assert first["module_name"] == "widget_maker"
    assert first["test_source"] == TEST_CONTENT

    gen_test_dir = repo_root / "verification" / "widget-maker" / "generated-test"
    if gen_test_dir.exists():
        assert [p for p in gen_test_dir.rglob("*") if p.is_file()] == []
    verification_dir = repo_root / "verification"
    if verification_dir.exists():
        assert [p for p in verification_dir.rglob("*") if p.is_file()] == []

    cache_dir = repo_root / ".hotdocs" / "cache"
    if cache_dir.exists():
        assert [p for p in cache_dir.rglob("*") if p.is_file()] == []