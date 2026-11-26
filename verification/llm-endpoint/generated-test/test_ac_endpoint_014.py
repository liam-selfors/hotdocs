# hotdocs-criterion: sha256:bc1f8b5d37045dfec21a23a5709d47438310155baa442b7cd2c69b39b1d9c9a2
import json
import os
import stat
import sys
from pathlib import Path

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


AUTH_KEY_HINT_MESSAGE = (
    "claude command failed (auth): ANTHROPIC_API_KEY is set, so claude used it "
    "instead of your claude.ai login; unset it, or set auth = \"login\" in "
    "hotdocs.toml's [llm] table"
)


def _write_config(work_dir, auth):
    text = "[llm]\n"
    text += "provider = \"claude-cli\"\n"
    text += "model = \"m\"\n"
    if auth is not None:
        text += "auth = " + json.dumps(auth) + "\n"
    (work_dir / "hotdocs.toml").write_text(text, encoding="utf-8")


def _write_recorder(bin_dir, log_path, mode):
    assistant_event = json.dumps(
        {
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "ok"}]},
        }
    )
    result_event = json.dumps(
        {"type": "result", "subtype": "success", "is_error": False, "result": "ok"}
    )
    src = "#!" + sys.executable + "\n"
    src += "# -*- coding: utf-8 -*-\n"
    src += "import json\n"
    src += "import os\n"
    src += "import sys\n"
    src += "LOG = " + repr(str(log_path)) + "\n"
    src += "MODE = " + repr(mode) + "\n"
    src += "with open(LOG, 'a', encoding='utf-8') as fh:\n"
    src += "    fh.write(json.dumps({'args': sys.argv[1:], 'key': os.environ.get('ANTHROPIC_API_KEY')}) + '\\n')\n"
    src += "try:\n"
    src += "    sys.stdin.read()\n"
    src += "except Exception:\n"
    src += "    pass\n"
    src += "if MODE == 'ok':\n"
    src += "    sys.stdout.write(" + repr(assistant_event + "\n") + ")\n"
    src += "    sys.stdout.write(" + repr(result_event + "\n") + ")\n"
    src += "    sys.stdout.flush()\n"
    src += "    sys.exit(0)\n"
    src += "elif MODE == 'stderr_invalid_key':\n"
    src += "    sys.stderr.write(" + repr("Invalid API key\n") + ")\n"
    src += "    sys.stderr.flush()\n"
    src += "    sys.exit(1)\n"
    src += "else:\n"
    src += "    sys.stdout.buffer.write(" + repr("Not logged in \u00b7 Please run /login\n") + ".encode('utf-8'))\n"
    src += "    sys.stdout.flush()\n"
    src += "    sys.exit(1)\n"
    path = bin_dir / "claude"
    path.write_text(src, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH | stat.S_IRUSR)
    return path


def _setup(tmp_path, monkeypatch, auth, mode, api_key):
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "recorder.log"
    _write_config(work_dir, auth)
    _write_recorder(bin_dir, log_path, mode)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.chdir(work_dir)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    if api_key is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", api_key)
    return log_path


def _records(log_path):
    assert log_path.is_file(), "the claude recorder was never run"
    lines = [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def test_auth_login_uses_safe_mode_and_strips_api_key(tmp_path, monkeypatch):
    log_path = _setup(tmp_path, monkeypatch, "login", "ok", "k1")
    response = llm_endpoint.complete("hi", "m")
    records = _records(log_path)
    assert len(records) == 1
    args = records[0]["args"]
    assert "--safe-mode" in args
    assert "--bare" not in args
    assert records[0]["key"] is None
    assert field(response, "model_call_error") is None
    assert field(response, "text") == "ok"


def test_auth_key_uses_bare_and_keeps_api_key(tmp_path, monkeypatch):
    log_path = _setup(tmp_path, monkeypatch, "key", "ok", "k1")
    response = llm_endpoint.complete("hi", "m")
    records = _records(log_path)
    assert len(records) == 1
    args = records[0]["args"]
    assert "--bare" in args
    assert records[0]["key"] == "k1"
    assert field(response, "model_call_error") is None


def test_unset_auth_with_key_invalid_key_gives_hint_message(tmp_path, monkeypatch):
    log_path = _setup(tmp_path, monkeypatch, None, "stderr_invalid_key", "k1")
    response = llm_endpoint.complete("hi", "m")
    _records(log_path)
    error = field(response, "model_call_error")
    assert error is not None
    assert {"category": field(error, "category"), "message": field(error, "message")} == {
        "category": "auth",
        "message": AUTH_KEY_HINT_MESSAGE,
    }
    assert field(response, "text") is None


def test_unset_auth_without_key_not_logged_in_gives_plain_message(tmp_path, monkeypatch):
    log_path = _setup(tmp_path, monkeypatch, None, "stdout_not_logged_in", None)
    response = llm_endpoint.complete("hi", "m")
    _records(log_path)
    error = field(response, "model_call_error")
    assert error is not None
    assert {"category": field(error, "category"), "message": field(error, "message")} == {
        "category": "auth",
        "message": "claude command failed (auth)",
    }
    assert field(response, "text") is None


def test_auth_key_invalid_key_gives_plain_message(tmp_path, monkeypatch):
    log_path = _setup(tmp_path, monkeypatch, "key", "stderr_invalid_key", "k1")
    response = llm_endpoint.complete("hi", "m")
    _records(log_path)
    error = field(response, "model_call_error")
    assert error is not None
    assert {"category": field(error, "category"), "message": field(error, "message")} == {
        "category": "auth",
        "message": "claude command failed (auth)",
    }
    assert field(response, "text") is None