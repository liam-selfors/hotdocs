import dataclasses
import json
import logging
import re
import secrets
from pathlib import Path

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class _Bundle:
    """A CriterionBundle stand-in readable both by attribute and as a mapping."""

    _FIELDS = (
        "component_id",
        "criterion_id",
        "covers",
        "criterion_text",
        "requirement_text",
        "interface",
        "glossary",
        "dependency_interfaces",
        "module_names",
    )

    def __init__(self, **kwargs):
        for name in self._FIELDS:
            setattr(self, name, kwargs.get(name))

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self._FIELDS:
            value = getattr(self, key)
            return default if value is None else value
        return default

    def __contains__(self, key):
        return key in self._FIELDS

    def keys(self):
        return list(self._FIELDS)

    def items(self):
        return [(k, getattr(self, k)) for k in self._FIELDS]

    def values(self):
        return [getattr(self, k) for k in self._FIELDS]

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)


def _to_text(value):
    parts = [repr(value)]
    data = None
    if isinstance(value, dict):
        data = value
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        try:
            data = dataclasses.asdict(value)
        except Exception:
            data = None
    if data is None and hasattr(value, "__dict__"):
        data = dict(vars(value))
    if data is not None:
        parts.append(json.dumps(data, default=repr, sort_keys=True))
    return "\n".join(parts)


def test_api_key_never_appears_in_result_or_logs(tmp_path, monkeypatch, caplog, capfd):
    secret_value = "sk-ant-api03-SENTINEL-" + secrets.token_hex(24)
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret_value)
    monkeypatch.setenv("VAR_ANTHROPIC_API_KEY", secret_value)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    caplog.set_level(logging.DEBUG)

    bundle = _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text="Given x = 2\nWhen foo(x) is called\nThen it returns 4",
        requirement_text="# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )

    expected_body = "import foo\n\n\ndef test_foo():\n    assert foo.foo(2) == 4\n"
    call_log = tmp_path / "backend_calls.log"

    def backend(prompt, model, **params):
        with open(call_log, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        nonces = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        assert nonces, "prompt carries no BEGIN FILE nonce"
        n = nonces[0]
        text = "-----BEGIN FILE " + n + "-----\n" + expected_body + "-----END FILE " + n + "-----"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    model = "anthropic:claude-sonnet-5"
    result = test_author.author_test(
        bundle, model, 0, repo_root=repo_root, llm_backend=backend
    )

    # It was a successful call.
    assert field(result, "model_call_error") is None
    assert call_log.is_file()

    # The result, in every rendering, never holds the key.
    result_text = _to_text(result)
    file_value = field(result, "file")
    result_text += "\n" + _to_text(file_value)
    assert secret_value not in result_text

    # Only the model identifier is recorded.
    recorded_model = field(result, "model")
    assert secret_value not in str(recorded_model)
    assert "claude-sonnet-5" in str(recorded_model)

    # Python logging records.
    for record in caplog.records:
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        assert secret_value not in message
        assert secret_value not in repr(record.args)
    assert secret_value not in caplog.text

    # Anything printed to stdout/stderr.
    out, err = capfd.readouterr()
    assert secret_value not in out
    assert secret_value not in err

    # Every file written anywhere under the temp area: the test file, the
    # cache, call logs, provenance, whatever else.
    secret_bytes = secret_value.encode("utf-8")
    for path in tmp_path.rglob("*"):
        if path.is_file():
            data = path.read_bytes()
            assert secret_bytes not in data, "API key leaked into " + str(path)