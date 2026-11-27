# hotdocs-criterion: sha256:0913f19c0456f206f06914c4b23d0f156ec1b99f06525602707c6a6674f1efbd
import json
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_probe_stand_in(repo_root, log_path):
    target = repo_root / "gen" / "test-probe" / "test_probe.py"
    target.parent.mkdir(parents=True, exist_ok=True)
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
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'test_source': test_source,\n"
        "                             'module_name': module_name}) + '\\n')\n"
        "    findings = [{'kind': 'test_bug', 'severity': 'error', 'line': 1,\n"
        "                 'message': 'stand-in rejects every test'}]\n"
        "    return ProbeReport(False, findings, 0, 0)\n"
    )
    target.write_text(source, encoding="utf-8")


def _read_calls(log_path):
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_probe_rejection_validates_extracted_test_and_writes_nothing(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, log_path)
    monkeypatch.chdir(repo_root)

    replies = []

    def mock_backend(prompt, model, **params):
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        content = (
            "import widget_maker\n"
            "\n"
            "\n"
            "def test_make_widget_" + str(len(replies)) + "():\n"
            "    assert widget_maker.make_widget('a') == 'a'\n"
        )
        replies.append(content)
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
        "criterion_text": "Given a name When make_widget is called Then it returns the name",
        "requirement_text": "R-WIDGET-MAKER-001 make_widget MUST return its name.",
        "interface": "make_widget(name: str) -> str",
        "glossary": "",
        "dependency_interfaces": {},
    }

    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=mock_backend
    )
    assert result is not None

    assert replies, "the mock model was never called"
    calls = _read_calls(log_path)
    assert calls, "the test-probe stand-in was never called"

    first = calls[0]
    assert first["module_name"] == "widget_maker"
    assert first["test_source"] == replies[0]
    for call in calls:
        assert call["module_name"] == "widget_maker"

    gen_test_dir = repo_root / "verification" / "widget-maker" / "generated-test"
    if gen_test_dir.exists():
        assert [p for p in gen_test_dir.rglob("*") if p.is_file()] == []
    verification = repo_root / "verification"
    if verification.exists():
        assert [p for p in verification.rglob("*") if p.is_file()] == []

    file_value = field(result, "file")
    if file_value is not None:
        assert not (repo_root / field(file_value, "path")).exists()