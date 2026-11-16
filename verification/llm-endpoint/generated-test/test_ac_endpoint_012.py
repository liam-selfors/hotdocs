import json
import os
import stat
import sys

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SUCCESS_LINES = [
    {"type": "system"},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "ab"}]}},
    {
        "type": "assistant",
        "message": {"content": [{"type": "thinking"}, {"type": "text", "text": "cd"}]},
    },
    {"type": "result", "is_error": False},
]

ERROR_LINES = SUCCESS_LINES[:-1] + [{"type": "result", "is_error": True}]


def _install_recorder(tmp_path, monkeypatch, stdout_text):
    """Put a fake `claude` command first on PATH.

    It records its argv (as JSON) to a file the test controls, writes
    `stdout_text` verbatim to stdout, and exits 0.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    record_path = tmp_path / "recorded_argv.json"
    payload_path = tmp_path / "recorder_stdout.txt"
    payload_path.write_bytes(stdout_text.encode("utf-8"))

    script = bin_dir / "claude"
    script.write_text(
        "#!" + sys.executable + "\n"
        "import json, sys\n"
        "with open(" + repr(str(record_path)) + ", 'w', encoding='utf-8') as fh:\n"
        "    json.dump(sys.argv[1:], fh)\n"
        "with open(" + repr(str(payload_path)) + ", 'rb') as fh:\n"
        "    data = fh.read()\n"
        "sys.stdout.buffer.write(data)\n"
        "sys.stdout.buffer.flush()\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    return record_path


def _stream(lines):
    return "".join(json.dumps(line) + "\n" for line in lines)


def _read_argv(record_path):
    assert record_path.exists(), "the claude recorder was never invoked"
    return json.loads(record_path.read_text(encoding="utf-8"))


def test_stream_json_text_blocks_joined_in_order(tmp_path, monkeypatch):
    record_path = _install_recorder(tmp_path, monkeypatch, _stream(SUCCESS_LINES))

    response = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert field(response, "text") == "abcd"
    assert field(response, "model_call_error") is None

    argv = _read_argv(record_path)
    assert "--output-format" in argv
    idx = argv.index("--output-format")
    assert idx + 1 < len(argv) and argv[idx + 1] == "stream-json", argv
    assert "--verbose" in argv, argv


def test_stream_json_result_is_error_is_failure(tmp_path, monkeypatch):
    record_path = _install_recorder(tmp_path, monkeypatch, _stream(ERROR_LINES))

    response = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert field(response, "text") is None
    assert field(response, "model_call_error") is not None
    assert record_path.exists()


def test_non_stream_output_is_reply_unchanged(tmp_path, monkeypatch):
    record_path = _install_recorder(tmp_path, monkeypatch, "hello\n")

    response = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert field(response, "model_call_error") is None
    assert field(response, "text") == "hello\n"
    assert record_path.exists()