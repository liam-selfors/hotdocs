# hotdocs-criterion: sha256:d4f02ae287ea03644478ba90859aa94b30f930296b6a0c1f48e9c5716997c178
import re

import test_author


EXPECTED_LINE = (
    "- Every `requirements/` file of every fixture component has a matching "
    "`acceptance/` file with a `Covers:` tag."
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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
        "        return {\"ok\": self.ok, \"findings\": list(self.findings),\n"
        "                \"tests_run\": self.tests_run, \"tests_reached\": self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None, drivers=None):\n"
        "    with open(" + repr(str(log_path)) + ", \"a\", encoding=\"utf-8\") as fh:\n"
        "        fh.write(\"probe\\n\")\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def _bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget, when made, then it exists.",
        "requirement_text": "R-WIDGET-MAKER-001 - widgets MUST be made.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_prompt_holds_fixture_acceptance_rule_line(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        body = "import widget_maker\n\n\ndef test_ok():\n    assert widget_maker is not None\n"
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + body
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        _bundle(), "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "model_call_error") is None
    assert prompts, "the mock model was never called"
    first_prompt = prompts[0]
    assert EXPECTED_LINE in first_prompt.splitlines()