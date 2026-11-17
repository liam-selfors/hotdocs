# hotdocs-criterion: sha256:b1c690e4752c8972b48ed08820ffbb5b82eccbf003369d902ee61d6113418a59
import logging
import os
import re
import secrets
from pathlib import Path

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle(dict):
    """A CriterionBundle readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


RESULT_FIELDS = [
    "component_id",
    "criterion_id",
    "model",
    "seed",
    "prompt_version",
    "cache_hit",
    "file",
    "model_call_error",
]


def _make_bundle():
    return Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4\n"
        ),
        requirement_text="# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


def test_api_key_never_appears_in_result_or_logs(tmp_path, monkeypatch, caplog, capsys):
    secret = "sk-ant-api03-SECRETKEY" + secrets.token_hex(24)
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    monkeypatch.setenv("VAR_ANTHROPIC_API_KEY", secret)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(tmp_path)

    calls_log = tmp_path / "backend_calls.log"
    body_text = "def test_placeholder():\n    assert 2 * 2 == 4"

    def mock_backend(prompt, model, **params):
        with open(calls_log, "a") as fh:
            fh.write("call\n")
        match = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        nonce = match.group(1) if match else ""
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + body_text + "\n"
            + "-----END FILE " + nonce + "-----"
        )
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
        0,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    # The call must be a successful one.
    assert field(result, "model_call_error") is None
    file_value = field(result, "file")
    assert file_value is not None
    content = field(file_value, "content")
    assert isinstance(content, str) and content
    assert calls_log.is_file()
    assert calls_log.read_text().count("call") >= 1

    # TestAuthoringResult: no field, nor its overall representation, holds the key.
    assert secret not in repr(result)
    assert secret not in str(result)
    for name in RESULT_FIELDS:
        value = field(result, name)
        assert secret not in repr(value), name
        assert secret not in str(value), name
    assert secret not in str(field(file_value, "path"))
    assert secret not in content

    # Logs captured through the logging module.
    assert secret not in caplog.text
    for record in caplog.records:
        assert secret not in record.getMessage()
        assert secret not in repr(record.args)

    # Anything printed to stdout/stderr.
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err

    # Any file written (output file, cache entries, call logs, provenance)
    # under repo_root or the working directory.
    secret_bytes = secret.encode("utf-8")
    for root in (repo_root, tmp_path):
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                path = Path(dirpath) / filename
                try:
                    data = path.read_bytes()
                except OSError:
                    continue
                assert secret_bytes not in data, str(path)