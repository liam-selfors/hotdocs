# hotdocs-criterion: sha256:76bda1c94c414601882f322950db490b618f25acc3fd9df16b94128cdd65d935
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

VALID_TEST_FILE = "def test_placeholder():\n    assert True\n"

NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def _setup_repo(repo_root, monkeypatch):
    repo_root.mkdir(parents=True, exist_ok=True)
    probe_dir = repo_root / "gen" / "test-probe"
    probe_dir.mkdir(parents=True, exist_ok=True)
    (probe_dir / "test_probe.py").write_text(PROBE_STANDIN_SOURCE, encoding="utf-8")
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def _make_mock(prompts):
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


def _base_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 - The widget MUST be made.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def test_prompt_holds_lint_block_with_derived_module_name(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo_derived"
    _setup_repo(repo_root, monkeypatch)
    prompts = []
    bundle = _base_bundle()

    test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=_make_mock(prompts)
    )

    assert prompts, "mock model was never called"
    first = prompts[0]
    lines = first.splitlines()
    assert "    import widget_maker" in lines
    assert "    assert spec_linter.lint(None, repo_root).hard_failures == 0" in lines
    assert "@MODULE@" not in first


def test_prompt_uses_first_module_name_when_given(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo_module_names"
    _setup_repo(repo_root, monkeypatch)
    prompts = []
    bundle = _base_bundle()
    bundle["module_names"] = ["alpha_mod", "beta_mod"]

    test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=_make_mock(prompts)
    )

    assert prompts, "mock model was never called"
    lines = prompts[0].splitlines()
    assert "    import alpha_mod" in lines
    assert "    import widget_maker" not in lines