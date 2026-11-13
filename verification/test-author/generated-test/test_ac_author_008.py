import dataclasses
import json
import logging
import re
import sys
from pathlib import Path

import test_author


SECRET_VALUE = "sk-ant-api03-ZZtopSecretQQ-NeverLeakThisKeyXYZ-abcdefGHIJKLmnopQRSTuvwxYZ"
MODEL = "claude-sonnet-5"


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _to_plain(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _to_plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): _to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_to_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "__dict__"):
        return {str(k): _to_plain(v) for k, v in vars(value).items()}
    return str(value)


def _make_bundle():
    return {
        "component_id": "comp-foo",
        "criterion_id": "AC-FOO-001",
        "covers": "R-FOO-001",
        "criterion_text": "Given x = 2\nWhen foo(x) is called\nThen it returns 4",
        "requirement_text": "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        "interface": "# Library\n\n```\nfoo(x: int) -> int\n```",
        "glossary": "# Glossary\n\n- **Foo** — a test term.",
        "dependency_interfaces": {},
        "module_names": ["foo"],
    }


def _make_backend(log_path: Path):
    def backend(prompt, model, **params):
        match = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt)
        if match is None:
            match = re.search(r"\b([0-9a-f]{32})\b", prompt)
        nonce = match.group(1) if match else "0" * 32
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model, "nonce": nonce}) + "\n")
        content = (
            "import foo\n"
            "\n"
            "\n"
            "def test_ac_foo_001():\n"
            "    assert foo.foo(2) == 4\n"
        )
        text = f"-----BEGIN FILE {nonce}-----\n{content}-----END FILE {nonce}-----\n"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _assert_secret_absent_from_result(result):
    assert SECRET_VALUE not in repr(result)
    assert SECRET_VALUE not in str(result)
    plain = _to_plain(result)
    assert SECRET_VALUE not in json.dumps(plain, default=str)


def _assert_successful(result):
    assert result is not None
    assert _get(result, "model_call_error") is None
    file_entry = _get(result, "file")
    assert file_entry is not None
    content = _get(file_entry, "content")
    assert isinstance(content, str) and content.strip() != ""
    model = _get(result, "model")
    assert model is not None
    assert "claude-sonnet-5" in str(model)


def _scan_tree_for_secret(root: Path):
    offenders = []
    secret_bytes = SECRET_VALUE.encode("utf-8")
    for path in root.rglob("*"):
        if path.is_file():
            try:
                data = path.read_bytes()
            except OSError:
                continue
            if secret_bytes in data:
                offenders.append(str(path))
    return offenders


def test_api_key_never_appears_in_result_or_logs(tmp_path, monkeypatch, capsys, caplog):
    caplog.set_level(logging.DEBUG)

    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET_VALUE)
    monkeypatch.setenv("VAR_ANTHROPIC_API_KEY", SECRET_VALUE)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    work_dir = tmp_path / "work"
    work_dir.mkdir()
    monkeypatch.chdir(work_dir)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    control_dir = tmp_path / "control"
    control_dir.mkdir()
    invocation_log = control_dir / "backend_calls.jsonl"

    backend = _make_backend(invocation_log)

    first = test_author.author_test(
        _make_bundle(), MODEL, 0, repo_root=repo_root, llm_backend=backend
    )
    _assert_successful(first)
    _assert_secret_absent_from_result(first)

    # A second identical call (possibly served from cache) must also be clean.
    second = test_author.author_test(
        _make_bundle(), MODEL, 0, repo_root=repo_root, llm_backend=backend
    )
    _assert_successful(second)
    _assert_secret_absent_from_result(second)

    # The mock backend actually ran at least once, and was never handed the key.
    assert invocation_log.is_file()
    calls_text = invocation_log.read_text(encoding="utf-8")
    assert calls_text.strip() != ""
    assert SECRET_VALUE not in calls_text

    # Python logging output.
    assert SECRET_VALUE not in caplog.text
    for record in caplog.records:
        assert SECRET_VALUE not in record.getMessage()
        assert SECRET_VALUE not in repr(record.args)

    # stdout / stderr.
    captured = capsys.readouterr()
    assert SECRET_VALUE not in captured.out
    assert SECRET_VALUE not in captured.err

    # Every file written anywhere under the test's own temp tree: call logs
    # (.hotdocs/calls/), cache entries (.hotdocs/cache/), written test files,
    # provenance, or anything else.
    offenders = _scan_tree_for_secret(tmp_path)
    assert offenders == [], f"API key value leaked into files: {offenders}"