# hotdocs-criterion: sha256:60b696789a4d539a1b28634529d8c760defb233a5cd51650603b7efc0f9f8354
import re

import test_author


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

VALID_TEST_FILE = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_widget():\n"
    "    assert widget_maker.make() is not None\n"
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
        "        return {\n"
        "            'ok': self.ok,\n"
        "            'findings': list(self.findings),\n"
        "            'tests_run': self.tests_run,\n"
        "            'tests_reached': self.tests_reached,\n"
        "        }\n"
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
        nonce = NONCE_RE.findall(prompt)[-1]
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

    probe_log = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, probe_log)

    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget, When made, Then it exists.",
        "requirement_text": "R-WIDGET-MAKER-001 - make MUST return a widget.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }

    prompts = []
    backend = make_mock_backend(prompts)

    test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=backend
    )

    assert prompts, "the mock model was never called"
    first = prompts[0]
    lines = first.splitlines()

    assert (
        "The component under test itself needs no custom loader: a plain `import widget_maker`."
        in lines
    )
    assert (
        "A dependency is never interceptable by name-based `sys.modules` injection or `mock.patch`."
        in lines
    )

    sys_modules_line = "        sys.modules[module_name] = module"
    exec_line = "        spec.loader.exec_module(module)"
    assert sys_modules_line in lines
    assert exec_line in lines
    assert lines.index(sys_modules_line) < lines.index(exec_line)