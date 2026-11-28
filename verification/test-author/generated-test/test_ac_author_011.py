# hotdocs-criterion: sha256:eaf1f575409b92324b1f99fd7fea1249ce32eccbbe7e5d5024f5c77f4d97cccf
import re

import test_author


SIGNATURE = "zq_lookup(x: int, y: str) -> ZqResult"
RULE_LINE = "a fake MUST return every field, never a bare list, string or number in its place"

REPLY_FILE = "def test_placeholder():\n    assert 1 + 1 == 2\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle(dependency_interfaces):
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - The widget MUST be made.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "dependency_interfaces": dependency_interfaces,
    }


def plant_probe_stand_in(repo_root, log_path):
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
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_mock_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
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

    return backend


def run_author(tmp_path, monkeypatch, dependency_interfaces):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_calls.log"
    plant_probe_stand_in(repo_root, log_path)
    prompts = []
    backend = make_mock_backend(prompts)
    result = test_author.author_test(
        make_bundle(dependency_interfaces),
        "mock",
        repo_root=repo_root,
        llm_backend=backend,
    )
    return result, prompts


def test_prompt_includes_dependency_interface_and_fake_rule(tmp_path, monkeypatch):
    result, prompts = run_author(
        tmp_path, monkeypatch, {"comp-zebra-quux": SIGNATURE}
    )
    assert prompts, "the mock model was never called"
    first = prompts[0]
    assert isinstance(first, str)
    assert "comp-zebra-quux" in first
    assert SIGNATURE in first
    assert RULE_LINE in first


def test_empty_dependency_interfaces_adds_no_entry(tmp_path, monkeypatch):
    result, prompts = run_author(tmp_path, monkeypatch, {})
    assert field(result, "model_call_error") is None
    assert prompts, "the mock model was never called"
    first = prompts[0]
    assert isinstance(first, str)
    assert "comp-zebra-quux" not in first