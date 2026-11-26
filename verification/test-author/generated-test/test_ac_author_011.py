# hotdocs-criterion: sha256:ccb33b1fe05ad04dc6d0da779e9f510df44d12b682aa13c2b8b904f08558bbc5
import re

import test_author


DEP_ID = "comp-zebra-quux"
DEP_INTERFACE = "zq_lookup(x: int, y: str) -> ZqResult"
FAKE_RULE = "a fake MUST return every field, never a bare list, string or number in its place"

NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

REPLY_FILE = "def test_placeholder():\n    assert True\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle(dependency_interfaces):
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - A widget MUST be made.",
        "interface": "make_widget() -> dict",
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
        "        return {'ok': True, 'findings': [], 'tests_run': 1, 'tests_reached': 1}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
        "          interpreter=None, assets=None, drivers=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as f:\n"
        "        f.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_mock(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = NONCE_RE.findall(prompt)[-1]
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


def run(tmp_path, monkeypatch, name, dependency_interfaces):
    repo_root = tmp_path / name
    repo_root.mkdir()
    log_path = tmp_path / (name + "-probe.log")
    plant_probe_stand_in(repo_root, log_path)
    monkeypatch.chdir(repo_root)
    prompts = []
    result = test_author.author_test(
        make_bundle(dependency_interfaces),
        "mock",
        repo_root=repo_root,
        llm_backend=make_mock(prompts),
    )
    return result, prompts


def test_dependency_interfaces_in_prompt(tmp_path, monkeypatch):
    result, prompts = run(
        tmp_path, monkeypatch, "with-deps", {DEP_ID: DEP_INTERFACE}
    )
    assert prompts, "the mock model was never called"
    first = prompts[0]
    assert DEP_ID in first
    assert DEP_INTERFACE in first
    assert FAKE_RULE in first


def test_empty_dependency_interfaces_adds_no_entry(tmp_path, monkeypatch):
    result, prompts = run(tmp_path, monkeypatch, "no-deps", {})
    assert field(result, "model_call_error") is None
    assert prompts, "the mock model was never called"
    assert DEP_ID not in prompts[0]