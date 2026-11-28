# hotdocs-criterion: sha256:8bcb835d72ad45af7f9b13ef6824212124ae8f401b4e638fe1556f50c542f2de
import re

import test_author


FIRST_FRAGMENT = "(`datetime.now(timezone.utc).replace(microsecond=0)`)"
SECOND_FRAGMENT = (
    "never comparing a timestamp truncated on write against "
    "microsecond-precision bounds."
)

MARKED_TEST_FILE = (
    "import test_author\n"
    "\n"
    "\n"
    "def test_placeholder():\n"
    "    assert test_author is not None\n"
)


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
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
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget, When made, Then it exists.",
        "requirement_text": "R-WIDGET-MAKER-001 The maker MUST make widgets.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_prompt_holds_write_time_window_precision_block(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + MARKED_TEST_FILE
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    test_author.author_test(
        _bundle(), "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert prompts, "the mock model was never called"
    first_prompt = prompts[0]
    assert FIRST_FRAGMENT in first_prompt
    assert SECOND_FRAGMENT in first_prompt