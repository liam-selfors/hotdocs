# hotdocs-criterion: sha256:fe8f4326d4197e8a23a25702729cca8f330c3756151457e6ea20de1231cfb307
import re

import test_author


PROBE_SOURCE_TEMPLATE_HEAD = (
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
)


def _probe_source(log_path):
    return (
        PROBE_SOURCE_TEMPLATE_HEAD
        + "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, **kwargs):\n"
        + "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        + "        fh.write('probe\\n')\n"
        + "    return _Report()\n"
    )


def test_prompt_holds_dependency_resolution_block(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_log = tmp_path / "probe_calls.log"
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True)
    (probe_dir / "test_probe.py").write_text(_probe_source(probe_log), encoding="utf-8")

    prompts = []
    test_file = "def test_something():\n    assert True\n"

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
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
        "requirement_text": "R-WIDGET-MAKER-001 The maker MUST make widgets.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }

    test_author.author_test(bundle, "mock", repo_root=repo_root, llm_backend=mock_backend)

    assert prompts, "the mock model was never called"
    lines = prompts[0].splitlines()

    assert (
        "The component under test itself needs no custom loader: a plain `import widget_maker`."
        in lines
    )
    assert (
        "A dependency is never interceptable by name-based `sys.modules` injection or `mock.patch`."
        in lines
    )

    inject_line = "        sys.modules[module_name] = module"
    exec_line = "        spec.loader.exec_module(module)"
    assert inject_line in lines
    assert exec_line in lines
    assert lines.index(inject_line) < lines.index(exec_line)