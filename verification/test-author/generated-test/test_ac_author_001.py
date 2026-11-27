# hotdocs-criterion: sha256:74bfcf7d8e9871abc2500ef6196cacc0205ddc54077a3e8893e974e2a926b6a8
import re

import test_author


CRITERION_TEXT = (
    "Given a zorblax widget ZQ-CRITERION-7781 When the maker spins "
    "Then the widget is quarvish"
)
REQUIREMENT_TEXT = (
    "R-WIDGET-MAKER-001 ZQ-REQUIREMENT-4412: the widget maker MUST spin "
    "every zorblax widget until it is quarvish"
)
INTERFACE_TEXT = (
    "make_widget(name: str) -> Widget ZQ-INTERFACE-9093 returns a "
    "quarvish widget"
)
GLOSSARY_TEXT = (
    "Quarvish ZQ-GLOSSARY-2267 means a widget that has been spun "
    "at least once"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_probe_stand_in(repo_root, log_path):
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
        "                \"tests_run\": self.tests_run,\n"
        "                \"tests_reached\": self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", \"a\") as handle:\n"
        "        handle.write(\"probe\\n\")\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source)


def test_prompt_holds_criterion_requirement_interface_and_glossary(
    tmp_path, monkeypatch
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, probe_log)

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        body = "def test_placeholder():\n    assert True\n"
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
    }

    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=mock_backend
    )

    assert result is not None
    assert field(result, "criterion_id") == "AC-WIDGET-MAKER-001"

    assert len(recorded) >= 1, "the mock model was never called"
    prompt = recorded[0]
    assert isinstance(prompt, str)

    assert CRITERION_TEXT in prompt
    assert REQUIREMENT_TEXT in prompt
    assert INTERFACE_TEXT in prompt
    assert GLOSSARY_TEXT in prompt