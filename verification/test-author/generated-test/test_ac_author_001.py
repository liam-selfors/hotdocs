# hotdocs-criterion: sha256:c4f1689c5ffe81a2fca77240c823ea069eed1b421e432acf19a2198601edf3b4
import re

import test_author


CRITERION_TEXT = (
    "Given a zorbulated widget quux-7731 When frobnicate is called "
    "Then the widget reports state plinth-4482"
)
REQUIREMENT_TEXT = (
    "R-WIDGET-MAKER-001 the widget maker MUST frobnicate every "
    "zorbulated widget into state marrow-9915"
)
INTERFACE_TEXT = (
    "# Library\n\nfrobnicate(widget: str) -> WidgetState  # iface-token-5526"
)
GLOSSARY_TEXT = (
    "- **Zorbulation** gloss-token-8834: the act of preparing a widget "
    "for frobnication"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_probe_stand_in(repo_root, log_path):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    source = (
        "LOG = " + repr(str(log_path)) + "\n"
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
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write('probe\\n')\n"
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
        body = (
            "import widget_maker\n"
            "\n"
            "\n"
            "def test_frobnicate():\n"
            "    assert widget_maker.frobnicate('w') is not None\n"
        )
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

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": CRITERION_TEXT,
        "requirement_text": REQUIREMENT_TEXT,
        "interface": INTERFACE_TEXT,
        "glossary": GLOSSARY_TEXT,
        "dependency_interfaces": {},
        "testing": "",
    }

    test_author.author_test(
        bundle,
        "mock",
        0,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert recorded, "the mock model was never called"
    prompt = recorded[0]
    assert isinstance(prompt, str)

    assert CRITERION_TEXT in prompt
    assert REQUIREMENT_TEXT in prompt
    assert INTERFACE_TEXT in prompt
    assert GLOSSARY_TEXT in prompt