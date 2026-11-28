# hotdocs-criterion: sha256:031f18290e9a9c079a9d7bf7108ea2d24256c8b18bc7a32f2f54cddb3b3a8f5f
# AC-AUTHOR-020: every extracted test is validated by test-probe's probe(),
# with the extracted content and the derived module name, and a test whose
# probe report is not ok is never written.
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
        "GATE_VERSION = 'test-probe@1.5.0'\n"
        "\n"
        "_LOG = " + repr(str(log_path)) + "\n"
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
        "    with open(_LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'test_source': test_source,\n"
        "                             'module_name': module_name}) + '\\n')\n"
        "    findings = [{'kind': 'undefined_name', 'severity': 'error',\n"
        "                 'line': 1, 'message': " + repr("undefined name 'nope'") + "}]\n"
        "    return ProbeReport(False, findings, 0, 0)\n"
    )
    target.write_text(source, encoding="utf-8")


def _reply_content(index):
    return (
        "import widget_maker\n"
        "\n"
        "\n"
        "def test_reply_" + str(index) + "():\n"
        "    assert widget_maker.make() is not None\n"
    )


def test_probe_called_with_extracted_content_and_module_name_and_nothing_written(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    log_path = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, log_path)

    replies = []

    def mock_backend(prompt, model, **params):
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        content = _reply_content(len(replies))
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
        "criterion_text": "Given a widget\nWhen make() is called\nThen a widget is returned",
        "requirement_text": "R-WIDGET-MAKER-001 make() MUST return a widget.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }

    test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert replies, "the mock model was never called"
    assert log_path.is_file(), "the test-probe stand-in was never called"
    calls = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert calls, "the test-probe stand-in was never called"

    first = calls[0]
    assert first["module_name"] == "widget_maker"
    assert first["test_source"] == replies[0]

    for call in calls:
        assert call["module_name"] == "widget_maker"

    generated_dir = repo_root / "verification" / "widget-maker" / "generated-test"
    assert not generated_dir.exists() or not any(
        p.is_file() for p in generated_dir.rglob("*")
    )
    verification = repo_root / "verification"
    written = [p for p in verification.rglob("*") if p.is_file()] if verification.exists() else []
    assert written == []