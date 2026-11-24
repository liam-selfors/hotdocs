# hotdocs-criterion: sha256:bb79c549d22b9699af33f98916c6d81e8310c40f39962de50291faa2a42b44cc
import re

import test_author


PROBE_SOURCE = (
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
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
    "          interpreter=None, assets=None):\n"
    "    return _Report()\n"
)

VALID_TEST = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_widget():\n"
    "    assert widget_maker.make() is not None\n"
)


def _make_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget, When made, Then it exists.",
        "requirement_text": "R-WIDGET-MAKER-001 The maker MUST make a widget.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_prompt_holds_dependency_resolution_block(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True)
    (probe_dir / "test_probe.py").write_text(PROBE_SOURCE, encoding="utf-8")

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + VALID_TEST
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    test_author.author_test(
        _make_bundle(), "mock", repo_root=repo_root, llm_backend=mock_backend
    )

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

    insert_line = "        sys.modules[module_name] = module"
    exec_line = "        spec.loader.exec_module(module)"
    assert insert_line in lines
    assert exec_line in lines
    assert lines.index(insert_line) < lines.index(exec_line)