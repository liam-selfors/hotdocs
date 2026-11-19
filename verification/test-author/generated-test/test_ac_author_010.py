# hotdocs-criterion: sha256:1dd97e55706f76077807763bbaa00f0932d4ee8cbd2d0b187ed7ee19ecfecbea
import re

import test_author


PROBE_STANDIN_SOURCE = (
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
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
    "    return _Report()\n"
)

VALID_TEST_FILE = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_widget_maker_called():\n"
    "    widget_maker.make()\n"
)


def _write_probe_standin(repo_root):
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    (probe_dir / "test_probe.py").write_text(PROBE_STANDIN_SOURCE, encoding="utf-8")


def _make_mock(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + VALID_TEST_FILE
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_prompt_holds_dependency_resolution_block(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    _write_probe_standin(repo_root)

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget, When make() is called, Then a widget is made.",
        "requirement_text": "R-WIDGET-MAKER-001 - make() MUST make a widget.",
        "interface": "make() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }

    prompts = []
    backend = _make_mock(prompts)

    test_author.author_test(bundle, "mock", repo_root=repo_root, llm_backend=backend)

    assert prompts, "the mock model was never called"
    first_prompt = prompts[0]
    lines = first_prompt.splitlines()

    assert (
        "The component under test itself needs no custom loader: a plain `import widget_maker`."
        in lines
    )
    assert (
        "A dependency is never interceptable by name-based `sys.modules` injection or `mock.patch`."
        in lines
    )

    sys_modules_line = "        sys.modules[module_name] = module"
    exec_module_line = "        spec.loader.exec_module(module)"
    assert sys_modules_line in lines
    assert exec_module_line in lines
    assert lines.index(sys_modules_line) < lines.index(exec_module_line)