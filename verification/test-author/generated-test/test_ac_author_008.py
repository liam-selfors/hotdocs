# hotdocs-criterion: sha256:b1c690e4752c8972b48ed08820ffbb5b82eccbf003369d902ee61d6113418a59
import logging
import os
import re
import secrets
from pathlib import Path

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


_NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")

_EXTRACTED = (
    "import foo\n"
    "\n"
    "\n"
    "def test_foo_doubles():\n"
    "    assert foo.foo(2) == 4\n"
)


def _make_bundle():
    return _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4\n"
        ),
        requirement_text="**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.\n",
        dependency_interfaces={},
        module_names=["foo"],
    )


def _all_text_under(root):
    chunks = []
    for p in Path(root).rglob("*"):
        chunks.append(str(p))
        if p.is_file():
            try:
                chunks.append(p.read_bytes().decode("utf-8", errors="ignore"))
            except OSError:
                pass
    return "\n".join(chunks)


def test_api_key_never_appears_in_result_or_logs(tmp_path, monkeypatch, caplog, capsys):
    api_key = "sk-ant-api03-SENTINEL" + secrets.token_hex(24)
    monkeypatch.setenv("ANTHROPIC_API_KEY", api_key)
    monkeypatch.setenv("VAR_ANTHROPIC_API_KEY", api_key)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)

    calls_log = tmp_path / "backend_calls.log"

    def backend(prompt, model, **params):
        with open(calls_log, "a") as fh:
            fh.write("call\n")
        m = _NONCE_RE.search(prompt)
        assert m is not None, "prompt carries no BEGIN FILE nonce"
        n = m.group(1)
        text = "-----BEGIN FILE " + n + "-----\n" + _EXTRACTED + "\n-----END FILE " + n + "-----"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    caplog.set_level(logging.DEBUG)

    result = test_author.author_test(
        _make_bundle(),
        "claude-sonnet-5",
        seed=0,
        repo_root=repo_root,
        llm_backend=backend,
    )

    # The call was successful.
    assert field(result, "model_call_error") is None
    file_obj = field(result, "file")
    assert file_obj is not None
    content = field(file_obj, "content")
    assert isinstance(content, str) and content
    assert calls_log.is_file() or field(result, "cache_hit")

    # Nothing in the TestAuthoringResult carries the key.
    for name in (
        "component_id",
        "criterion_id",
        "model",
        "seed",
        "prompt_version",
        "cache_hit",
        "file",
        "model_call_error",
    ):
        value = field(result, name)
        assert api_key not in repr(value), name
        assert api_key not in str(value), name
    assert api_key not in repr(result)
    assert api_key not in str(result)
    assert api_key not in content
    assert api_key not in str(field(file_obj, "path"))

    # Nothing logged through `logging` carries the key.
    assert api_key not in caplog.text
    for record in caplog.records:
        assert api_key not in record.getMessage()
        assert api_key not in repr(record.args)

    # Nothing printed carries the key.
    captured = capsys.readouterr()
    assert api_key not in captured.out
    assert api_key not in captured.err

    # Nothing written to disk (written test file, cache, call logs, provenance) carries the key.
    assert api_key not in _all_text_under(repo_root)
    assert api_key not in _all_text_under(tmp_path)