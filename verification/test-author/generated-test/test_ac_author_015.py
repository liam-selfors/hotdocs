# hotdocs-criterion: sha256:76bda1c94c414601882f322950db490b618f25acc3fd9df16b94128cdd65d935
import re
from pathlib import Path

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
    "        return {'ok': self.ok, 'findings': list(self.findings), "
    "'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, "
    "interpreter=None, assets=None):\n"
    "    return _Report()\n"
)

GOOD_FILE = "def test_placeholder():\n    assert True\n"


def _plant_probe(repo_root):
    d = Path(repo_root) / "gen" / "test-probe"
    d.mkdir(parents=True, exist_ok=True)
    (d / "test_probe.py").write_text(PROBE_SOURCE, encoding="utf-8")


def _make_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        n = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + n + "-----\n"
            + GOOD_FILE
            + "\n-----END FILE " + n + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _bundle(**extra):
    b = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 The maker MUST make widgets.",
        "interface": "make() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }
    b.update(extra)
    return b


def _setup(tmp_path, monkeypatch, name):
    repo_root = tmp_path / name
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    _plant_probe(repo_root)
    return repo_root


def test_prompt_holds_lint_block_with_derived_module(tmp_path, monkeypatch):
    repo_root = _setup(tmp_path, monkeypatch, "s1")
    prompts = []
    test_author.author_test(
        _bundle(), "mock", repo_root=repo_root, llm_backend=_make_backend(prompts)
    )
    assert prompts, "the mock model was never called"
    first = prompts[0]
    lines = first.splitlines()
    assert "    import widget_maker" in lines
    assert "    assert spec_linter.lint(None, repo_root).hard_failures == 0" in lines
    assert "@MODULE@" not in first


def test_prompt_uses_first_module_name(tmp_path, monkeypatch):
    repo_root = _setup(tmp_path, monkeypatch, "s2")
    prompts = []
    test_author.author_test(
        _bundle(module_names=["alpha_mod", "beta_mod"]),
        "mock",
        repo_root=repo_root,
        llm_backend=_make_backend(prompts),
    )
    assert prompts, "the mock model was never called"
    lines = prompts[0].splitlines()
    assert "    import alpha_mod" in lines
    assert "    import widget_maker" not in lines