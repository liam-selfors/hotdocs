# hotdocs-criterion: sha256:f97e6dd001dee9ef878fcba94a01849f0bdaca4afc67b46c4f99a1bd1803b5f0
import re
from pathlib import Path

import test_author


ZQ_ID = "comp-zebra-quux"
ZQ_INTERFACE = "zq_lookup(x: int, y: str) -> ZqResult"
FAKE_RULE = "a fake MUST return every field, never a bare list, string or number in its place"

TEST_FILE = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_widget():\n"
    "    assert widget_maker.make() is not None\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle(dependency_interfaces):
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen make() is called\nThen a widget is returned",
        "requirement_text": "R-WIDGET-MAKER-001 make() MUST return a widget.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": dependency_interfaces,
    }


def write_probe_stand_in(repo_root, log_path):
    probe_dir = Path(repo_root) / "gen" / "test-probe"
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_mock(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonces = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        n = nonces[-1]
        text = (
            "-----BEGIN FILE " + n + "-----\n"
            + TEST_FILE
            + "\n-----END FILE " + n + "-----"
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
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    log_path = tmp_path / (name + "-probe.log")
    write_probe_stand_in(repo_root, log_path)
    prompts = []
    result = test_author.author_test(
        make_bundle(dependency_interfaces),
        "mock",
        repo_root=repo_root,
        llm_backend=make_mock(prompts),
    )
    return result, prompts


def test_prompt_includes_dependency_interfaces_and_fake_rule(tmp_path, monkeypatch):
    result, prompts = run(tmp_path, monkeypatch, "with-deps", {ZQ_ID: ZQ_INTERFACE})
    assert prompts, "mock model was never called"
    first = prompts[0]
    assert ZQ_ID in first
    assert ZQ_INTERFACE in first
    assert FAKE_RULE in first


def test_empty_dependency_interfaces_adds_no_entry(tmp_path, monkeypatch):
    result, prompts = run(tmp_path, monkeypatch, "no-deps", {})
    assert field(result, "model_call_error") is None
    assert prompts, "mock model was never called"
    assert ZQ_ID not in prompts[0]