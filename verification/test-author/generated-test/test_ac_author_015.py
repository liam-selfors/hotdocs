# hotdocs-criterion: sha256:976a3aaa41310d3a136115e9e07a2ff770aa3fe7c4fefa3be6d60ff135a775e6
import re
from pathlib import Path

import test_author


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32})-----"

TEST_FILE = "def test_placeholder():\n    assert True\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write_probe_stand_in(repo_root, log_path):
    base = Path(repo_root) / "gen" / "test-probe"
    base.mkdir(parents=True, exist_ok=True)
    source = (
        "import dataclasses\n"
        "\n"
        "GATE_VERSION = 'test-probe@1.4.0'\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class ProbeReport:\n"
        "    ok: bool\n"
        "    findings: list\n"
        "    tests_run: int\n"
        "    tests_reached: int\n"
        "\n"
        "    def to_dict(self):\n"
        "        return dataclasses.asdict(self)\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None, assets=None):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return ProbeReport(ok=True, findings=[], tests_run=1, tests_reached=1)\n"
    )
    (base / "test_probe.py").write_text(source, encoding="utf-8")


def make_backend(prompts):
    def backend(prompt, model, **params):
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

    return backend


def base_bundle():
    return {
        "component_id": "comp-widget-maker",
        "criterion_id": "AC-WIDGET-MAKER-001",
        "covers": "R-WIDGET-MAKER-001",
        "criterion_text": "Given a widget, When it is made, Then it exists.",
        "requirement_text": "R-WIDGET-MAKER-001 - The maker MUST make widgets.",
        "interface": "make_widget(name: str) -> dict",
        "glossary": "",
        "dependency_interfaces": {},
    }


def run_author(repo_root, bundle, monkeypatch):
    repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(repo_root)
    log_path = repo_root / "probe_calls.log"
    write_probe_stand_in(repo_root, log_path)
    prompts = []
    result = test_author.author_test(
        bundle, "mock", repo_root=repo_root, llm_backend=make_backend(prompts)
    )
    assert prompts, "the mock model was never called"
    return result, prompts


def test_prompt_holds_lint_block_with_derived_module(tmp_path, monkeypatch):
    repo_root = tmp_path / "scenario1"
    bundle = base_bundle()
    result, prompts = run_author(repo_root, bundle, monkeypatch)

    first = prompts[0]
    lines = first.splitlines()
    assert "    import widget_maker" in lines
    assert "    assert spec_linter.lint(None, repo_root).hard_failures == 0" in lines
    assert "@MODULE@" not in first
    assert field(result, "model_call_error") is None


def test_prompt_uses_first_module_name(tmp_path, monkeypatch):
    repo_root = tmp_path / "scenario2"
    bundle = base_bundle()
    bundle["module_names"] = ["alpha_mod", "beta_mod"]
    result, prompts = run_author(repo_root, bundle, monkeypatch)

    first = prompts[0]
    lines = first.splitlines()
    assert "    import alpha_mod" in lines
    assert "    import widget_maker" not in lines
    assert field(result, "model_call_error") is None