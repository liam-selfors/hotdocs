# hotdocs-criterion: sha256:273a7d009b69b57519ca5055b894eeee20edab5c290312f931a3a50aada3a16a
import re

import test_author


PROBE_STAND_IN_SOURCE = (
    "class _Report:\n"
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
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None, assets=None):\n"
    "    return _Report()\n"
)


GOOD_TEST_FILE = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_widget():\n"
    "    assert widget_maker.make() is not None\n"
)


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - A widget MUST be made.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_prompt_holds_write_time_window_precision_block(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    probe_dir = tmp_path / "gen" / "test-probe"
    probe_dir.mkdir(parents=True)
    (probe_dir / "test_probe.py").write_text(PROBE_STAND_IN_SOURCE, encoding="utf-8")

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + GOOD_TEST_FILE
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    test_author.author_test(
        _bundle(), "mock", repo_root=tmp_path, llm_backend=mock_backend
    )

    assert prompts, "the mock model was never called"
    first = prompts[0]
    assert "(`datetime.now(timezone.utc).replace(microsecond=0)`)" in first
    assert (
        "never comparing a timestamp truncated on write against microsecond-precision bounds."
        in first
    )