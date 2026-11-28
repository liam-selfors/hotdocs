# hotdocs-criterion: sha256:b2a5fa8f63e6e161c493d43fa1986a90c726b6ea9107293d1321a6358b57cec8
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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


def _make_mock(prompts):
    body = "def test_generated():\n    assert True\n"

    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)[-1]
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + body
            + "\n-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _bundle(**extra):
    bundle = {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 — The maker MUST make widgets.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }
    bundle.update(extra)
    return bundle


def test_prompt_holds_lint_block_with_derived_module_name(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo1"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    _write_probe_stand_in(repo_root, tmp_path / "probe1.log")
    prompts = []
    mock = _make_mock(prompts)

    result = test_author.author_test(
        _bundle(), "mock", repo_root=repo_root, llm_backend=mock
    )

    assert field(result, "model_call_error") is None
    assert prompts, "the mock model was never called"
    first = prompts[0]
    lines = first.splitlines()
    assert "    import widget_maker" in lines
    assert "    assert spec_linter.lint(None, repo_root).hard_failures == 0" in lines
    assert "@MODULE@" not in first


def test_prompt_uses_first_module_name_when_given(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo2"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    _write_probe_stand_in(repo_root, tmp_path / "probe2.log")
    prompts = []
    mock = _make_mock(prompts)

    result = test_author.author_test(
        _bundle(module_names=["alpha_mod", "beta_mod"]),
        "mock",
        repo_root=repo_root,
        llm_backend=mock,
    )

    assert field(result, "model_call_error") is None
    assert prompts, "the mock model was never called"
    lines = prompts[0].splitlines()
    assert "    import alpha_mod" in lines
    assert "    import widget_maker" not in lines