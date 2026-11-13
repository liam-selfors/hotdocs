import json
import re
import sys
from pathlib import Path

import pytest

import test_author


DEP_INTERFACE_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "do_the_thing(x: int, y: str) -> SomeResult\n"
    "```\n"
    "\n"
    "`SomeResult` is a record with fields `zorblax_marker_7731: str` and\n"
    "`quillon_count_4410: int`, in that order.\n"
)

TARGET_INTERFACE_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "widget_total(n: int) -> int\n"
    "```\n"
)

GLOSSARY_TEXT = "# Glossary\n\n- **Widget** — a test term.\n"

MOCK_TEST_FILE = "def test_placeholder():\n    assert True\n"


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _make_bundle(criterion_id, covers, dependency_interfaces):
    return _Bundle(
        component_id="comp-widget",
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=(
            "Given n = 3\n"
            "When widget_total(n) is called\n"
            "Then it returns 6"
        ),
        requirement_text=(
            "# " + covers + "\n\n**" + covers + "** — `widget_total(n)` MUST return `2 * n`."
        ),
        interface=TARGET_INTERFACE_TEXT,
        glossary=GLOSSARY_TEXT,
        dependency_interfaces=dict(dependency_interfaces),
        module_names=["widget"],
    )


def _make_backend(log_path):
    nonce_re = re.compile(r"-----BEGIN FILE ([0-9a-fA-F]{32})-----")
    any_hex_re = re.compile(r"\b([0-9a-f]{32})\b")

    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        m = nonce_re.search(prompt)
        nonce = m.group(1) if m else None
        if nonce is None:
            m2 = any_hex_re.search(prompt)
            nonce = m2.group(1) if m2 else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + MOCK_TEST_FILE
            + "-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _read_prompts(log_path):
    if not Path(log_path).is_file():
        return []
    prompts = []
    for line in Path(log_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            prompts.append(json.loads(line)["prompt"])
    return prompts


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    work = tmp_path / "cwd"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "logs" / "prompts.jsonl"
    log_path.parent.mkdir()
    return repo_root, log_path


def test_prompt_includes_dependency_interface_and_fake_fidelity_instruction(isolated_env):
    repo_root, log_path = isolated_env
    bundle = _make_bundle(
        "AC-WIDGET-011",
        "R-WIDGET-011",
        {"comp-bar": DEP_INTERFACE_TEXT},
    )

    result = test_author.author_test(
        bundle,
        "claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=_make_backend(log_path),
    )

    prompts = _read_prompts(log_path)
    assert prompts, "the model backend was never called, so no prompt was sent"
    prompt = prompts[0]

    # The exact dependency interface text is included verbatim.
    assert DEP_INTERFACE_TEXT.strip() in prompt
    assert "do_the_thing(x: int, y: str) -> SomeResult" in prompt
    assert "comp-bar" in prompt

    # An instruction that fakes must match the real signature and return
    # shape, never inventing one. None of these words appear in the bundle's
    # own texts, so they must come from the prompt's instructions.
    lowered = prompt.lower()
    assert "fake" in lowered
    assert "signature" in lowered
    assert "return" in lowered
    assert "shape" in lowered
    assert "invent" in lowered

    assert _field(result, "model_call_error") is None
    file_value = _field(result, "file")
    assert file_value is not None
    content = _field(file_value, "content")
    assert content is not None
    assert "def test_placeholder" in content


def test_prompt_builds_with_no_dependencies_and_claims_none(isolated_env):
    repo_root, log_path = isolated_env
    bundle = _make_bundle("AC-WIDGET-012", "R-WIDGET-012", {})

    result = test_author.author_test(
        bundle,
        "claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=_make_backend(log_path),
    )

    prompts = _read_prompts(log_path)
    assert prompts, "the prompt did not build / the model backend was never called"
    for prompt in prompts:
        assert "comp-bar" not in prompt
        assert "do_the_thing" not in prompt
        assert "SomeResult" not in prompt
        assert "zorblax_marker_7731" not in prompt

    assert _field(result, "model_call_error") is None
    file_value = _field(result, "file")
    assert file_value is not None
    content = _field(file_value, "content")
    assert content is not None
    assert "def test_placeholder" in content