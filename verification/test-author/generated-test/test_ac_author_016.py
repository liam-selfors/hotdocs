# hotdocs-criterion: sha256:099b97ef12ce5d5b08109d1496cbac2e492cc9768ba750204f1a7d7c9499d275
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
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {\n"
        "            " + repr("ok") + ": self.ok,\n"
        "            " + repr("findings") + ": list(self.findings),\n"
        "            " + repr("tests_run") + ": self.tests_run,\n"
        "            " + repr("tests_reached") + ": self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(LOG_PATH, " + repr("a") + ", encoding=" + repr("utf-8") + ") as fh:\n"
        "        fh.write(" + repr("probe") + " + " + repr("\n") + ")\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def test_prompt_holds_requirements_acceptance_covers_line(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    recorded_prompts = []
    test_file = (
        "import widget_maker\n"
        "\n"
        "\n"
        "def test_something():\n"
        "    assert widget_maker.make() is not None\n"
    )

    def mock_backend(prompt, model, **params):
        recorded_prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + test_file
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
        "criterion_text": "Given a widget, When made, Then it exists.",
        "requirement_text": "R-WIDGET-MAKER-001 - make() MUST return a widget.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }

    test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert recorded_prompts, "the mock model was never called"
    first_prompt = recorded_prompts[0]
    assert EXPECTED_LINE in first_prompt.splitlines()