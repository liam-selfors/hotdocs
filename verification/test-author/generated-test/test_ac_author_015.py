# hotdocs-criterion: sha256:1abcc1e54bb3953fd46bcfe00f3edaaef6a985408cdee16b6fc1d2956637a4d0
import re

import test_author


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

TEST_FILE = "def test_placeholder():\n    assert True\n"


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


def make_mock(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = NONCE_RE.findall(prompt)[-1]
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

    return backend


def base_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget\nWhen it is made\nThen it exists",
        "requirement_text": "R-WIDGET-MAKER-001 — The maker MUST make widgets.",
        "interface": "make_widget() -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def run_author(repo_root, monkeypatch, bundle):
    repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(repo_root)
    log_path = repo_root / "probe_calls.log"
    write_probe_stand_in(repo_root, log_path)
    prompts = []
    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=make_mock(prompts)
    )
    assert prompts, "the mock model was never called"
    return result, prompts


def test_lint_block_with_derived_module_name(tmp_path, monkeypatch):
    repo_root = tmp_path / "scenario1"
    bundle = base_bundle()
    result, prompts = run_author(repo_root, monkeypatch, bundle)

    first = prompts[0]
    lines = first.splitlines()
    assert "    import widget_maker" in lines
    assert "    assert spec_linter.lint(None, repo_root).hard_failures == 0" in lines
    assert "@MODULE@" not in first
    assert field(result, "model_call_error") is None


def test_lint_block_uses_first_module_name(tmp_path, monkeypatch):
    repo_root = tmp_path / "scenario2"
    bundle = base_bundle()
    bundle["module_names"] = ["alpha_mod", "beta_mod"]
    result, prompts = run_author(repo_root, monkeypatch, bundle)

    first = prompts[0]
    lines = first.splitlines()
    assert "    import alpha_mod" in lines
    assert "    import widget_maker" not in lines
    assert field(result, "model_call_error") is None