# hotdocs-criterion: sha256:c21a115e9a04258be629aefbd4e15cd3513fac645439b3abade8425ced02a84b
import json
import os
import stat
import sys
from pathlib import Path

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


STREAM_PREFIX = [
    '{"type": "system"}',
    '{"type": "assistant", "message": {"content": [{"type": "text", "text": "ab"}]}}',
    '{"type": "assistant", "message": {"content": [{"type": "thinking"}, {"type": "text", "text": "cd"}]}}',
]


def write_recorder(bin_dir, log_path, stdout_text, exit_code=0):
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / "claude"
    source = (
        "#!" + sys.executable + "\n"
        "import json\n"
        "import os\n"
        "import sys\n"
        "try:\n"
        "    sys.stdin.read()\n"
        "except Exception:\n"
        "    pass\n"
        "with open(" + repr(str(log_path)) + ", 'a') as fh:\n"
        "    fh.write(json.dumps({'argv': sys.argv[1:], 'key': os.environ.get('ANTHROPIC_API_KEY')}) + '\\n')\n"
        "sys.stdout.write(" + repr(stdout_text) + ")\n"
        "sys.stdout.flush()\n"
        "sys.exit(" + repr(exit_code) + ")\n"
    )
    script.write_text(source)
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return script


def setup_env(tmp_path, monkeypatch, stdout_text, exit_code=0):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    bin_dir = tmp_path / "bin"
    log_path = tmp_path / "calls.log"
    write_recorder(bin_dir, log_path, stdout_text, exit_code)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    return log_path


def read_log(log_path):
    if not log_path.exists():
        return []
    return [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]


def test_stream_json_reply_is_joined_text_blocks(tmp_path, monkeypatch):
    lines = STREAM_PREFIX + ['{"type": "result", "is_error": false}']
    log_path = setup_env(tmp_path, monkeypatch, "\n".join(lines) + "\n", 0)

    resp = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert field(resp, "text") == "abcd"
    assert field(resp, "model_call_error") is None

    records = read_log(log_path)
    assert len(records) == 1
    argv = records[0]["argv"]
    assert "--output-format" in argv
    idx = argv.index("--output-format")
    assert idx + 1 < len(argv)
    assert argv[idx + 1] == "stream-json"
    assert "--verbose" in argv


def test_stream_result_is_error_is_failure(tmp_path, monkeypatch):
    lines = STREAM_PREFIX + ['{"type": "result", "is_error": true}']
    log_path = setup_env(tmp_path, monkeypatch, "\n".join(lines) + "\n", 0)

    resp = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert field(resp, "text") is None
    err = field(resp, "model_call_error")
    assert err is not None
    assert len(read_log(log_path)) == 1


def test_non_stream_stdout_is_reply_unchanged(tmp_path, monkeypatch):
    log_path = setup_env(tmp_path, monkeypatch, "hello\n", 0)

    resp = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert field(resp, "text") == "hello\n"
    assert field(resp, "model_call_error") is None
    assert len(read_log(log_path)) == 1