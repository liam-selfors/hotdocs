# hotdocs-criterion: sha256:f3a58e7d006e7fcd84ae51f86318840cfc8ffed083a306ddb164a0c12ba68486
import re

import test_author


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

GOOD_TEST = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_make_widget():\n"
    "    assert widget_maker.make_widget() is not None\n"
)

EXPECTED_FRAGMENT_1 = "(`datetime.now(timezone.utc).replace(microsecond=0)`)"
EXPECTED_FRAGMENT_2 = (
    "never comparing a timestamp truncated on write against "
    "microsecond-precision bounds."
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "import json",
        "",
        "",
        "class _Report:",
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
        "def probe(test_source, criterion_bundle, module_name, **kwargs):",
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:",
        "        fh.write(json.dumps({'module_name': module_name}) + '\\n')",
        "    return _Report()",
        "",
    ]
    (probe_dir / "test_probe.py").write_text("\n".join(lines), encoding="utf-8")


def _make_mock_backend(recorded):
    def backend(prompt, model, **params):
        recorded.append(prompt)
        nonce = re.findall(NONCE_RE, prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + GOOD_TEST
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": (
            "Given nothing\nWhen make_widget() is called\n"
            "Then it returns a widget"
        ),
        "requirement_text": "R-WIDGET-MAKER-001 make_widget MUST return a widget.",
        "interface": "make_widget() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_prompt_holds_write_time_window_precision_block(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    recorded = []
    backend = _make_mock_backend(recorded)

    test_author.author_test(
        _bundle(), "mock", repo_root=repo_root, llm_backend=backend
    )

    assert recorded, "the mock model was never called"
    first_prompt = recorded[0]
    assert EXPECTED_FRAGMENT_1 in first_prompt
    assert EXPECTED_FRAGMENT_2 in first_prompt