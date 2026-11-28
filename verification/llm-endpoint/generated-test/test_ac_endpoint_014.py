# hotdocs-criterion: sha256:f4944de2cde4bb1d7ea476af75436abf0c5381b284cdcd1b66625fdccffb16de
import json
import os
import stat
import sys

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SUCCESS_BODY = (
    "sys.stdout.write(json.dumps("
    + repr({"type": "assistant", "message": {"content": [{"type": "text", "text": "ok"}]}})
    + ") + '\\n')\n"
    + "sys.stdout.write(json.dumps("
    + repr({"type": "result", "is_error": False, "result": "ok"})
    + ") + '\\n')\n"
    + "sys.exit(0)\n"
)

INVALID_KEY_BODY = (
    "sys.stderr.write(" + repr("Invalid API key") + " + '\\n')\n"
    + "sys.exit(1)\n"
)

NOT_LOGGED_IN_BODY = (
    "sys.stdout.write(" + repr("Not logged in \u00b7 Please run /login") + " + '\\n')\n"
    + "sys.exit(1)\n"
)


def write_recorder(bin_dir, log_path, body):
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / "claude"
    source = (
        "#!" + sys.executable + "\n"
        + "# -*- coding: utf-8 -*-\n"
        + "import json, os, sys\n"
        + "try:\n"
        + "    sys.stdin.read()\n"
        + "except Exception:\n"
        + "    pass\n"
        + "with open(" + repr(str(log_path)) + ", 'a', encoding='utf-8') as f:\n"
        + "    f.write(json.dumps({'args': sys.argv[1:], 'key': os.environ.get('ANTHROPIC_API_KEY')}) + '\\n')\n"
        + "sys.stdout.reconfigure(encoding='utf-8')\n"
        + "sys.stderr.reconfigure(encoding='utf-8')\n"
        + body
    )
    script.write_text(source, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script


def write_config(directory, auth):
    lines = ["[llm]", 'provider = "claude-cli"', 'model = "m"']
    if auth is not None:
        lines.append("auth = " + json.dumps(auth))
    (directory / "hotdocs.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def setup(tmp_path, monkeypatch, auth, body, api_key):
    work = tmp_path / "work"
    work.mkdir()
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "recorder.log"
    write_recorder(bin_dir, log_path, body)
    write_config(work, auth)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    if api_key is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", api_key)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.chdir(work)
    return log_path


def read_records(log_path):
    assert log_path.is_file(), "recorder never ran"
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


def test_auth_login_uses_safe_mode_and_strips_key(tmp_path, monkeypatch):
    log_path = setup(tmp_path, monkeypatch, "login", SUCCESS_BODY, "k1")
    response = llm_endpoint.complete("hi", "m")
    assert field(response, "model_call_error") is None
    records = read_records(log_path)
    assert len(records) == 1
    args = records[0]["args"]
    assert "--safe-mode" in args
    assert "--bare" not in args
    assert records[0]["key"] is None


def test_auth_key_uses_bare_and_keeps_key(tmp_path, monkeypatch):
    log_path = setup(tmp_path, monkeypatch, "key", SUCCESS_BODY, "k1")
    response = llm_endpoint.complete("hi", "m")
    assert field(response, "model_call_error") is None
    records = read_records(log_path)
    assert len(records) == 1
    args = records[0]["args"]
    assert "--bare" in args
    assert records[0]["key"] == "k1"


def test_unset_auth_with_key_invalid_key_gives_hint(tmp_path, monkeypatch):
    log_path = setup(tmp_path, monkeypatch, None, INVALID_KEY_BODY, "k1")
    response = llm_endpoint.complete("hi", "m")
    read_records(log_path)
    assert field(response, "model_call_error") == {
        "category": "auth",
        "message": (
            "claude command failed (auth): ANTHROPIC_API_KEY is set, so claude used it "
            "instead of your claude.ai login; unset it, or set auth = \"login\" in "
            "hotdocs.toml's [llm] table"
        ),
    }
    assert field(response, "text") is None


def test_unset_auth_without_key_not_logged_in(tmp_path, monkeypatch):
    log_path = setup(tmp_path, monkeypatch, None, NOT_LOGGED_IN_BODY, None)
    response = llm_endpoint.complete("hi", "m")
    read_records(log_path)
    assert field(response, "model_call_error") == {
        "category": "auth",
        "message": "claude command failed (auth)",
    }
    assert field(response, "text") is None


def test_auth_key_invalid_key_plain_message(tmp_path, monkeypatch):
    log_path = setup(tmp_path, monkeypatch, "key", INVALID_KEY_BODY, "k1")
    response = llm_endpoint.complete("hi", "m")
    read_records(log_path)
    assert field(response, "model_call_error") == {
        "category": "auth",
        "message": "claude command failed (auth)",
    }
    assert field(response, "text") is None