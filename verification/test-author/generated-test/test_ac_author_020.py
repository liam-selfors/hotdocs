# hotdocs-criterion: sha256:5fe86cf9982e82dff62c2fdcfb3eb3400bc26e37bb856a9c3ae37993c1ede373
import json
import re

import test_author


GENERATED_FILE = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_widget():\n"
    "    assert widget_maker.make() is not None\n"
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
        "            " + repr("ok") + ": self.ok,\n"
        "            " + repr("findings") + ": [dict(f) for f in self.findings],\n"
        "            " + repr("tests_run") + ": self.tests_run,\n"
        "            " + repr("tests_reached") + ": self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None, drivers=None):\n"
        "    with open(LOG_PATH, " + repr("a") + ", encoding=" + repr("utf-8") + ") as fh:\n"
        "        fh.write(json.dumps({" + repr("test_source") + ": test_source, "
        + repr("module_name") + ": module_name}) + " + repr("\n") + ")\n"
        "    findings = [{\n"
        "        " + repr("kind") + ": " + repr("undefined_name") + ",\n"
        "        " + repr("severity") + ": " + repr("error") + ",\n"
        "        " + repr("line") + ": 1,\n"
        "        " + repr("message") + ": " + repr("undefined name 'nope'") + ",\n"
        "    }]\n"
        "    return ProbeReport(False, findings, 0, 0)\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def test_ac_author_020_probe_called_with_extracted_content_and_rejected(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, log_path)
    monkeypatch.chdir(repo_root)

    replies = []

    def mock_backend(prompt, model, **params):
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + GENERATED_FILE
            + "\n-----END FILE " + nonce + "-----"
        )
        replies.append(text)
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
        "criterion_text": "Given a widget, When made, Then it exists.",
        "requirement_text": "R-WIDGET-MAKER-001 make() MUST return a widget.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }

    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=mock_backend
    )
    assert result is not None
    assert field(result, "criterion_id") == "AC-WIDGET-MAKER-001"

    assert replies, "the mock model was never called"
    assert log_path.is_file(), "the test-probe stand-in was never called"
    calls = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(calls) >= 1

    first = calls[0]
    assert first["module_name"] == "widget_maker"
    assert first["test_source"] == GENERATED_FILE

    target_dir = repo_root / "verification" / "widget-maker" / "generated-test"
    if target_dir.exists():
        assert [p for p in target_dir.rglob("*") if p.is_file()] == []
    verification = repo_root / "verification"
    if verification.exists():
        assert [p for p in verification.rglob("*") if p.is_file()] == []