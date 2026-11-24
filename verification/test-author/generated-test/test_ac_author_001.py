# hotdocs-criterion: sha256:0d81045a077845af01905cb85305552d15b0db268170b0ca123319ea0fda5e09
import re

import test_author


CRITERION_TEXT = (
    "Given a widget blueprint ZQX-CRITERION-MARKER-7731\n"
    "When make_widget is called\n"
    "Then the widget has the blueprint's colour"
)
REQUIREMENT_TEXT = (
    "**R-WIDGET-MAKER-001** - make_widget MUST build a widget from its "
    "blueprint, ZQX-REQUIREMENT-MARKER-4402."
)
INTERFACE_TEXT = (
    "# Library\n\n"
    "make_widget(blueprint: dict) -> Widget  # ZQX-INTERFACE-MARKER-9157\n"
)
GLOSSARY_TEXT = (
    "# Glossary\n\n"
    "- **Widget** - a thing made by widget-maker, ZQX-GLOSSARY-MARKER-2268.\n"
)

REPLY_FILE = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_make_widget():\n"
    "    assert widget_maker.make_widget({}) is not None\n"
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, "
        "interpreter=None, assets=None):\n"
        "    with open(LOG_PATH, " + repr("a") + ") as handle:\n"
        "        handle.write(" + repr("probe\n") + ")\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source)


def test_prompt_contains_criterion_requirement_interface_and_glossary(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        nonces = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        nonce = nonces[-1] if nonces else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + REPLY_FILE
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
        "criterion_text": CRITERION_TEXT,
        "requirement_text": REQUIREMENT_TEXT,
        "interface": INTERFACE_TEXT,
        "glossary": GLOSSARY_TEXT,
        "dependency_interfaces": {},
    }

    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=mock_backend
    )

    assert recorded, "the mock model was never called"
    assert field(result, "model_call_error") is None

    first_prompt = recorded[0]
    assert isinstance(first_prompt, str)
    assert CRITERION_TEXT in first_prompt
    assert REQUIREMENT_TEXT in first_prompt
    assert INTERFACE_TEXT.strip() in first_prompt
    assert GLOSSARY_TEXT.strip() in first_prompt