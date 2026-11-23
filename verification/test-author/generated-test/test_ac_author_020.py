# hotdocs-criterion: sha256:57444f95e6b084da68721fdf1c7ab9ee4c6c58d50d52d573c345c0609743fbea
import json
import re

import test_author


FIRST_CONTENT = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_first_reply():\n"
    "    assert widget_maker.make_widget('a') is not None"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _probe_stand_in_source(log_path):
    return (
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
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
        "        fh.write(json.dumps({'test_source': test_source,\n"
        "                             'module_name': module_name}) + '\\n')\n"
        "    return ProbeReport(\n"
        "        ok=False,\n"
        "        findings=[{'kind': 'test_bug', 'severity': 'error', 'line': 1,\n"
        "                   'message': 'test failed before reaching the code under test'}],\n"
        "        tests_run=1,\n"
        "        tests_reached=0,\n"
        "    )\n"
    )


def test_rejected_probe_is_not_written_or_cached(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    log_path = tmp_path / "probe_calls.log"
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True)
    (probe_dir / "test_probe.py").write_text(
        _probe_stand_in_source(log_path), encoding="utf-8"
    )

    calls = {"n": 0}

    def mock_backend(prompt, model, **params):
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        calls["n"] += 1
        if calls["n"] == 1:
            content = FIRST_CONTENT
        else:
            content = (
                "import widget_maker\n"
                "\n"
                "\n"
                "def test_repair_" + str(calls["n"]) + "():\n"
                "    assert widget_maker.make_widget('b') is not None"
            )
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

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget name When make_widget is called Then a widget is returned",
        "requirement_text": "R-WIDGET-MAKER-001 make_widget MUST return a widget.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }

    test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert log_path.is_file(), "test-probe stand-in was never called"
    lines = [
        line for line in log_path.read_text(encoding="utf-8").splitlines() if line
    ]
    assert lines, "test-probe stand-in was never called"
    records = [json.loads(line) for line in lines]

    first = records[0]
    assert first["module_name"] == "widget_maker"
    assert first["test_source"] == FIRST_CONTENT
    for rec in records:
        assert rec["module_name"] == "widget_maker"

    gen_test_dir = repo_root / "verification" / "widget-maker" / "generated-test"
    if gen_test_dir.exists():
        assert [p for p in gen_test_dir.rglob("*") if p.is_file()] == []
    verification = repo_root / "verification"
    if verification.exists():
        assert [p for p in verification.rglob("*") if p.is_file()] == []

    cache_dir = repo_root / ".hotdocs" / "cache"
    if cache_dir.exists():
        assert [p for p in cache_dir.rglob("*") if p.is_file()] == []