# hotdocs-criterion: sha256:553be697c52e50c77e809f8d009eb8c35857094100f8b01663a61471ffa60e0e
"""AC-GEN-003: every GenerationResult's prompt_version matches the frozen
template's declared version (R-GEN-003)."""

import re

import pytest

import generator


DECLARED_PROMPT_VERSION = "v12"
NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32}):"

FAKE_PYTHON_ADAPTER = (
    "from pathlib import Path\n"
    "\n"
    "KIND = \"python\"\n"
    "\n"
    "\n"
    "def layout_errors(code_dir):\n"
    "    return [\"bad.py:1: SyntaxError: x\"] if (Path(code_dir) / \"bad.py\").exists() else []\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"python\": \"3.12\"}, "
    "\"lockfile_sha256\": None, \"interpreter\": \"/fake/python\"}\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_repo(tmp_path, sealed=False):
    repo_root = tmp_path / "repo"
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(FAKE_PYTHON_ADAPTER, encoding="utf-8")
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    lines = [
        "---",
        "id: comp-widget-maker",
        "title: Widget Maker",
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: []",
    ]
    if sealed:
        lines.append("sealed: true")
        lines.append("source_path: legacy/widget-maker/")
    else:
        lines.append("sealed: false")
    lines += ["---", "", "# Widget Maker", ""]
    (comp_dir / "component.md").write_text("\n".join(lines), encoding="utf-8")
    return repo_root


def make_bundle(hint_code=None, spec="Make widgets."):
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "spec": spec,
        "interface": "make_widget() -> str",
        "constraints": "No network.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": hint_code,
    }


def ok_reply(prompt):
    nonce = re.search(NONCE_RE, prompt).group(1)
    return (
        "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
        + "def make_widget():\n"
        + "    return 'widget'\n"
        + "-----END FILE " + nonce + "-----\n"
        + "-----END REPLY " + nonce + "-----\n"
    )


def make_ok_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        return {"text": ok_reply(prompt), "model": model, "backend": "mock", "model_call_error": None}

    return backend


def make_error_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        return {
            "text": None,
            "model": model,
            "backend": "mock",
            "model_call_error": {"category": "network", "message": "backend unreachable"},
        }

    return backend


@pytest.fixture(autouse=True)
def _no_remote_cache(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def assert_version(result):
    assert field(result, "prompt_version") == generator.PROMPT_VERSION
    assert field(result, "prompt_version") == DECLARED_PROMPT_VERSION


def assert_prompt_declares_version(prompts):
    assert prompts, "the mock model was never called"
    declared_line = "PROMPT_VERSION: " + generator.PROMPT_VERSION
    for prompt in prompts:
        assert declared_line in prompt.split("\n")


def test_declared_constant_is_frozen_version():
    assert generator.PROMPT_VERSION == DECLARED_PROMPT_VERSION


@pytest.mark.parametrize("retry_feedback", [None, [], ["R-WIDGET-002", "R-WIDGET-001"]])
def test_cold_generation_records_prompt_version(tmp_path, retry_feedback):
    repo_root = make_repo(tmp_path)
    prompts = []
    result = generator.generate(
        make_bundle(), "mock-model", retry_feedback,
        repo_root=repo_root, llm_backend=make_ok_backend(prompts),
    )
    assert field(result, "files")
    assert field(result, "cache_hit") is False
    assert_version(result)
    assert_prompt_declares_version(prompts)


def test_hint_generation_records_prompt_version(tmp_path):
    repo_root = make_repo(tmp_path)
    prompts = []
    bundle = make_bundle(hint_code={"widget_maker.py": "def make_widget():\n    return 'old'\n"})
    result = generator.generate(
        bundle, "mock-model", None, repo_root=repo_root, llm_backend=make_ok_backend(prompts),
    )
    assert field(result, "files")
    assert_version(result)
    assert_prompt_declares_version(prompts)


def test_model_call_error_records_prompt_version(tmp_path):
    repo_root = make_repo(tmp_path)
    prompts = []
    result = generator.generate(
        make_bundle(spec="Error case."), "mock-model", None,
        repo_root=repo_root, llm_backend=make_error_backend(prompts),
    )
    assert field(result, "model_call_error") is not None
    assert_version(result)
    assert_prompt_declares_version(prompts)


def test_refused_generation_records_prompt_version(tmp_path):
    repo_root = make_repo(tmp_path, sealed=True)
    prompts = []
    result = generator.generate(
        make_bundle(spec="Sealed case."), "mock-model", None,
        repo_root=repo_root, llm_backend=make_ok_backend(prompts),
    )
    assert field(result, "refused") is not None
    assert prompts == []
    assert_version(result)


def test_cache_hit_records_prompt_version(tmp_path):
    repo_root = make_repo(tmp_path)
    prompts = []
    bundle = make_bundle(spec="Cache case.")
    first = generator.generate(
        bundle, "mock-model", None, repo_root=repo_root, llm_backend=make_ok_backend(prompts),
    )
    assert field(first, "files")
    assert_version(first)
    generator.commit_cache(first, repo_root=repo_root)

    second_prompts = []
    second = generator.generate(
        bundle, "mock-model", None, repo_root=repo_root, llm_backend=make_ok_backend(second_prompts),
    )
    assert field(second, "cache_hit") is True
    assert second_prompts == []
    assert_version(second)