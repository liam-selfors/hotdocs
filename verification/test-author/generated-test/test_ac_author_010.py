# hotdocs-criterion: sha256:14c951e5cf478bd1e436ab81915ad2a969df9b4ba03a5d5412a77d65cb1b9633
import re

import test_author


A_COMPONENT_LINE = (
    "The component under test itself needs no custom loader: "
    "a plain `import widget_maker`."
)
A_DEPENDENCY_LINE = (
    "A dependency is never interceptable by name-based `sys.modules` "
    "injection or `mock.patch`."
)
SYS_MODULES_LINE = "        sys.modules[module_name] = module"
EXEC_MODULE_LINE = "        spec.loader.exec_module(module)"

NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

TEST_FILE = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_make():\n"
    "    assert widget_maker.make() is not None\n"
)


def _write_probe_stand_in(repo_root, log_path):
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def test_prompt_holds_dependency_resolution_block(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    probe_log = tmp_path / "probe_calls.log"
    _write_probe_stand_in(repo_root, probe_log)

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(NONCE_RE, prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + TEST_FILE
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
        "criterion_text": (
            "Given nothing\nWhen make() is called\nThen it returns a widget"
        ),
        "requirement_text": "R-WIDGET-MAKER-001 make() MUST return a widget.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }

    test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=mock_backend
    )

    assert prompts, "the mock model was never called"
    first = prompts[0]
    lines = first.splitlines()

    assert A_COMPONENT_LINE in lines
    assert A_DEPENDENCY_LINE in lines

    assert SYS_MODULES_LINE in lines
    sys_index = lines.index(SYS_MODULES_LINE)
    assert EXEC_MODULE_LINE in lines[sys_index + 1:]