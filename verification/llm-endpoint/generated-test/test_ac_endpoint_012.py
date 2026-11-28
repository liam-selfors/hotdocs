# hotdocs-criterion: sha256:bb1a420e232a6035670b31ac9cc2d6fbb496049e3e258d0f247d287c8b0f6787
import json
import os
import stat
import sys

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


STREAM_LINES_OK = [
    '{"type": "system"}',
    '{"type": "assistant", "message": {"content": [{"type": "text", "text": "ab"}]}}',
    '{"type": "assistant", "message": {"content": [{"type": "thinking"}, {"type": "text", "text": "cd"}]}}',
    '{"type": "result", "is_error": false}',
]

STREAM_LINES_ERR = STREAM_LINES_OK[:-1] + ['{"type": "result", "is_error": true}']


def _install_recorder(tmp_path, monkeypatch, stdout_text, exit_code=0):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log_path = tmp_path / "claude_calls.log"
    script = (
        "#!" + sys.executable + "\n"
        + "import json\n"
        + "import os\n"
        + "import sys\n"
        + "try:\n"
        + "    sys.stdin.read()\n"
        + "except Exception:\n"
        + "    pass\n"
        + "with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        + "    f.write(json.dumps({'args': sys.argv[1:], 'key': os.environ.get('ANTHROPIC_API_KEY')}) + '\\n')\n"
        + "sys.stdout.write(" + repr(stdout_text) + ")\n"
        + "sys.stdout.flush()\n"
        + "sys.exit(" + repr(exit_code) + ")\n"
    )
    claude = bindir / "claude"
    claude.write_text(script)
    claude.chmod(claude.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return log_path


def _read_calls(log_path):
    assert log_path.is_file(), "the claude recorder was never run"
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def _holds_stream_json_verbose(args):
    for i in range(len(args) - 1):
        if args[i] == "--output-format" and args[i + 1] == "stream-json":
            return "--verbose" in args
    return False


def test_stream_reply_joins_text_blocks(tmp_path, monkeypatch):
    log_path = _install_recorder(tmp_path, monkeypatch, "\n".join(STREAM_LINES_OK) + "\n", 0)

    response = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert field(response, "text") == "abcd"
    assert field(response, "model_call_error") is None

    calls = _read_calls(log_path)
    assert len(calls) == 1
    args = calls[0]["args"]
    assert _holds_stream_json_verbose(args), args


def test_stream_result_is_error_is_failure(tmp_path, monkeypatch):
    log_path = _install_recorder(tmp_path, monkeypatch, "\n".join(STREAM_LINES_ERR) + "\n", 0)

    response = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert field(response, "text") is None
    error = field(response, "model_call_error")
    assert error is not None
    assert field(error, "category") in ("network", "auth", "rate_limit", "timeout")

    calls = _read_calls(log_path)
    assert len(calls) == 1


def test_non_stream_stdout_is_whole_reply(tmp_path, monkeypatch):
    log_path = _install_recorder(tmp_path, monkeypatch, "hello\n", 0)

    response = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert field(response, "text") == "hello\n"
    assert field(response, "model_call_error") is None

    calls = _read_calls(log_path)
    assert len(calls) == 1