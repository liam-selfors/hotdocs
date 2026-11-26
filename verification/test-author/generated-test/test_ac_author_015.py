# hotdocs-criterion: sha256:608728c9eb61f99ac3f7a07bfa4ca7c328d9b5513f451f9da2d834b8fa5a0d10
import re

import test_author


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
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, **kwargs):\n"
        "    with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    (probe_dir / "test_probe.py").write_text(source, encoding="utf-8")


def make_mock(prompts):
    test_file = "def test_placeholder():\n    assert True\n"

    def backend(prompt, model, **params):
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

    return backend


def base_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget, when it is made, then it exists.",
        "requirement_text": "R-WIDGET-MAKER-001 The maker MUST make widgets.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def run(tmp_path, monkeypatch, bundle):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    log_path = tmp_path / "probe_calls.log"
    write_probe_stand_in(repo_root, log_path)
    prompts = []
    backend = make_mock(prompts)
    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=backend
    )
    assert field(result, "model_call_error") is None
    assert len(prompts) >= 1
    return prompts


def test_prompt_holds_lint_block_with_derived_module(tmp_path, monkeypatch):
    bundle = base_bundle()
    prompts = run(tmp_path, monkeypatch, bundle)
    first = prompts[0]
    lines = first.splitlines()
    assert "    import widget_maker" in lines
    assert "    assert spec_linter.lint(None, repo_root).hard_failures == 0" in lines
    assert "@MODULE@" not in first


def test_prompt_uses_first_module_name(tmp_path, monkeypatch):
    bundle = base_bundle()
    bundle["module_names"] = ["alpha_mod", "beta_mod"]
    prompts = run(tmp_path, monkeypatch, bundle)
    first = prompts[0]
    lines = first.splitlines()
    assert "    import alpha_mod" in lines
    assert "    import widget_maker" not in lines