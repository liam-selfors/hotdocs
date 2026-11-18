# hotdocs-criterion: sha256:4d39fc9efc1ffe1df01ec53feaac020201b6da7bf3b3082d93f56882e54aa8e4
import json
import os
import stat
import sys

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SUCCESS_STREAM = [
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "hello"}]}},
    {"type": "result", "is_error": False, "result": "hello"},
]


def _write_recorder(bin_dir, log_path, stdout_text, stderr_text, exit_code):
    script = (
        "#!" + sys.executable + "\n"
        "import json, os, sys\n"
        "try:\n"
        "    sys.stdin.read()\n"
        "except Exception:\n"
        "    pass\n"
        "with open(%r, 'a', encoding='utf-8') as fh:\n"
        "    fh.write(json.dumps({'args': sys.argv[1:], "
        "'key': os.environ.get('ANTHROPIC_API_KEY')}) + '\\n')\n"
        "sys.stdout.buffer.write(%r.encode('utf-8'))\n"
        "sys.stdout.flush()\n"
        "sys.stderr.buffer.write(%r.encode('utf-8'))\n"
        "sys.stderr.flush()\n"
        "sys.exit(%d)\n"
    ) % (str(log_path), stdout_text, stderr_text, exit_code)
    path = bin_dir / "claude"
    path.write_text(script, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _setup(tmp_path, monkeypatch, auth, api_key, stdout_text, stderr_text, exit_code):
    work = tmp_path / "work"
    work.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "recorder.log"

    lines = ["[llm]", 'provider = "claude-cli"', 'model = "m"']
    if auth is not None:
        lines.append('auth = "%s"' % auth)
    (work / "hotdocs.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")

    _write_recorder(bin_dir, log_path, stdout_text, stderr_text, exit_code)

    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(work)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    if api_key is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", api_key)
    return log_path


def _records(log_path):
    assert log_path.exists(), "the claude recorder was never run"
    text = log_path.read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _success_stdout():
    return "".join(json.dumps(event) + "\n" for event in SUCCESS_STREAM)


def _error_dict(response):
    err = field(response, "model_call_error")
    assert err is not None
    return {"category": field(err, "category"), "message": field(err, "message")}


def test_auth_login_uses_safe_mode_and_strips_api_key(tmp_path, monkeypatch):
    log_path = _setup(tmp_path, monkeypatch, "login", "k1", _success_stdout(), "", 0)

    llm_endpoint.complete("hi", "m")

    records = _records(log_path)
    assert len(records) == 1
    args = records[0]["args"]
    assert "--safe-mode" in args
    assert "--bare" not in args
    assert records[0]["key"] is None


def test_auth_key_uses_bare_and_keeps_api_key(tmp_path, monkeypatch):
    log_path = _setup(tmp_path, monkeypatch, "key", "k1", _success_stdout(), "", 0)

    llm_endpoint.complete("hi", "m")

    records = _records(log_path)
    assert len(records) == 1
    args = records[0]["args"]
    assert "--bare" in args
    assert records[0]["key"] == "k1"


def test_unset_auth_with_key_invalid_api_key_gives_hint_message(tmp_path, monkeypatch):
    log_path = _setup(tmp_path, monkeypatch, None, "k1", "", "Invalid API key\n", 1)

    response = llm_endpoint.complete("hi", "m")

    assert len(_records(log_path)) == 1
    assert _error_dict(response) == {
        "category": "auth",
        "message": (
            "claude command failed (auth): ANTHROPIC_API_KEY is set, so claude used it "
            "instead of your claude.ai login; unset it, or set auth = \"login\" in "
            "hotdocs.toml's [llm] table"
        ),
    }


def test_unset_auth_without_key_not_logged_in_gives_plain_message(tmp_path, monkeypatch):
    log_path = _setup(
        tmp_path, monkeypatch, None, None,
        "Not logged in \u00b7 Please run /login\n", "", 1,
    )

    response = llm_endpoint.complete("hi", "m")

    assert len(_records(log_path)) == 1
    assert _error_dict(response) == {
        "category": "auth",
        "message": "claude command failed (auth)",
    }


def test_auth_key_invalid_api_key_gives_plain_message(tmp_path, monkeypatch):
    log_path = _setup(tmp_path, monkeypatch, "key", "k1", "", "Invalid API key\n", 1)

    response = llm_endpoint.complete("hi", "m")

    assert len(_records(log_path)) == 1
    assert _error_dict(response) == {
        "category": "auth",
        "message": "claude command failed (auth)",
    }