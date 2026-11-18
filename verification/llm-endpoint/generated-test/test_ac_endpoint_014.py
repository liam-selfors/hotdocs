# hotdocs-criterion: sha256:4d39fc9efc1ffe1df01ec53feaac020201b6da7bf3b3082d93f56882e54aa8e4
import json
import os
import stat
import sys

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SUCCESS_STDOUT = (
    json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "ok"}]}})
    + "\n"
    + json.dumps({"type": "result", "is_error": False, "result": "ok"})
    + "\n"
)

KEY_MESSAGE = (
    "claude command failed (auth): ANTHROPIC_API_KEY is set, so claude used it "
    "instead of your claude.ai login; unset it, or set auth = \"login\" in "
    "hotdocs.toml's [llm] table"
)


def write_config(directory, auth):
    lines = ["[llm]", 'provider = "claude-cli"', 'model = "m"']
    if auth is not None:
        lines.append("auth = " + json.dumps(auth))
    (directory / "hotdocs.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_recorder(bin_dir, log_path, stdout_text, stderr_text, exit_code):
    bin_dir.mkdir(parents=True, exist_ok=True)
    src_lines = [
        "#!" + sys.executable,
        "import json, os, sys",
        "try:",
        "    sys.stdin.read()",
        "except Exception:",
        "    pass",
        "with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as f:",
        "    f.write(json.dumps({'args': sys.argv[1:], 'key': os.environ.get('ANTHROPIC_API_KEY')}) + '\\n')",
        "sys.stdout.buffer.write(" + repr(stdout_text) + ".encode('utf-8'))",
        "sys.stdout.flush()",
        "sys.stderr.buffer.write(" + repr(stderr_text) + ".encode('utf-8'))",
        "sys.stderr.flush()",
        "sys.exit(" + repr(exit_code) + ")",
    ]
    script = bin_dir / "claude"
    script.write_text("\n".join(src_lines) + "\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script


def setup(tmp_path, monkeypatch, auth, key, stdout_text, stderr_text, exit_code):
    work = tmp_path / "work"
    work.mkdir()
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "calls.log"
    write_config(work, auth)
    write_recorder(bin_dir, log_path, stdout_text, stderr_text, exit_code)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(work)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    if key is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", key)
    return log_path


def read_records(log_path):
    assert log_path.is_file(), "the claude recorder was never run"
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_auth_login_uses_safe_mode_and_strips_key(tmp_path, monkeypatch):
    log_path = setup(tmp_path, monkeypatch, "login", "k1", SUCCESS_STDOUT, "", 0)
    response = llm_endpoint.complete("hi", "m")
    records = read_records(log_path)
    assert len(records) == 1
    args = records[0]["args"]
    assert "--safe-mode" in args
    assert "--bare" not in args
    assert records[0]["key"] is None
    assert field(response, "model_call_error") is None


def test_auth_key_uses_bare_and_keeps_key(tmp_path, monkeypatch):
    log_path = setup(tmp_path, monkeypatch, "key", "k1", SUCCESS_STDOUT, "", 0)
    response = llm_endpoint.complete("hi", "m")
    records = read_records(log_path)
    assert len(records) == 1
    args = records[0]["args"]
    assert "--bare" in args
    assert records[0]["key"] == "k1"
    assert field(response, "model_call_error") is None


def test_unset_auth_with_key_auth_failure_explains_login(tmp_path, monkeypatch):
    log_path = setup(tmp_path, monkeypatch, None, "k1", "", "Invalid API key\n", 1)
    response = llm_endpoint.complete("hi", "m")
    read_records(log_path)
    assert field(response, "text") is None
    assert field(response, "model_call_error") == {"category": "auth", "message": KEY_MESSAGE}


def test_unset_auth_without_key_not_logged_in(tmp_path, monkeypatch):
    log_path = setup(
        tmp_path, monkeypatch, None, None, "Not logged in \u00b7 Please run /login\n", "", 1
    )
    response = llm_endpoint.complete("hi", "m")
    read_records(log_path)
    assert field(response, "text") is None
    assert field(response, "model_call_error") == {
        "category": "auth",
        "message": "claude command failed (auth)",
    }


def test_auth_key_failure_gets_plain_message(tmp_path, monkeypatch):
    log_path = setup(tmp_path, monkeypatch, "key", "k1", "", "Invalid API key\n", 1)
    response = llm_endpoint.complete("hi", "m")
    read_records(log_path)
    assert field(response, "text") is None
    assert field(response, "model_call_error") == {
        "category": "auth",
        "message": "claude command failed (auth)",
    }