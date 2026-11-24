# hotdocs-criterion: sha256:37057a262526bbdc3dfd70f40a0b68604bd53ebe28cef5d2129998f16d380cf2
import json
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"


def _write_probe_stand_in(repo_root, log_path):
    base = repo_root / "gen" / "test-probe"
    base.mkdir(parents=True, exist_ok=True)
    source = (
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
        "    findings = [{\n"
        "        'kind': 'undefined_name',\n"
        "        'severity': 'error',\n"
        "        'line': 1,\n"
        "        'message': \"undefined name 'nowhere'\",\n"
        "    }]\n"
        "    return ProbeReport(False, findings, 0, 0)\n"
    )
    (base / "test_probe.py").write_text(source, encoding="utf-8")


def test_ac_author_020_probe_called_with_extracted_content_and_failing_test_not_written(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    log_path = tmp_path / "probe_calls.jsonl"
    _write_probe_stand_in(repo_root, log_path)

    replied_contents = []

    def mock_backend(prompt, model, **params):
        nonce = re.findall(NONCE_RE, prompt)[-1]
        index = len(replied_contents) + 1
        content = (
            "# reply " + str(index) + "\n"
            "import widget_maker\n"
            "\n"
            "\n"
            "def test_make_widget():\n"
            "    assert widget_maker.make_widget() is not None\n"
        )
        replied_contents.append(content)
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
        "criterion_text": "Given nothing When make_widget() is called Then a widget is returned",
        "requirement_text": "R-WIDGET-MAKER-001 make_widget MUST return a widget.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }

    test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert replied_contents, "the mock model was never called"
    assert log_path.is_file(), "the test-probe stand-in was never called"

    calls = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert calls, "the test-probe stand-in was never called"

    first = calls[0]
    assert first["module_name"] == "widget_maker"
    assert first["test_source"] == replied_contents[0]

    gen_test_dir = repo_root / "verification" / "widget-maker" / "generated-test"
    if gen_test_dir.exists():
        assert [p for p in gen_test_dir.rglob("*") if p.is_file()] == []

    verification = repo_root / "verification"
    if verification.exists():
        assert [p for p in verification.rglob("*") if p.is_file()] == []