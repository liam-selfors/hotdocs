import json
import os
import stat
import sys

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


STREAM_EVENTS_OK = [
    {"type": "system"},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "ab"}]}},
    {
        "type": "assistant",
        "message": {"content": [{"type": "thinking"}, {"type": "text", "text": "cd"}]},
    },
    {"type": "result", "is_error": False},
]

STREAM_EVENTS_ERROR = STREAM_EVENTS_OK[:-1] + [{"type": "result", "is_error": True}]


def _stream(events):
    return "".join(json.dumps(e) + "\n" for e in events)


def _install_recorder(tmp_path, monkeypatch, stdout_text, exit_code=0):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "claude_calls.log"
    script = bin_dir / "claude"
    script.write_text(
        "#!{exe}\n"
        "import sys, json, os\n"
        "try:\n"
        "    sys.stdin.read()\n"
        "except Exception:\n"
        "    pass\n"
        "with open({log!r}, 'a') as f:\n"
        "    f.write(json.dumps({{'argv': sys.argv[1:], "
        "'key': os.environ.get('ANTHROPIC_API_KEY')}}) + '\\n')\n"
        "sys.stdout.write({out!r})\n"
        "sys.stdout.flush()\n"
        "sys.exit({code})\n".format(
            exe=sys.executable,
            log=str(log_path),
            out=stdout_text,
            code=exit_code,
        )
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    return log_path


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return cwd


def _read_calls(log_path):
    assert log_path.exists(), "the claude recorder was never invoked"
    lines = [l for l in log_path.read_text().splitlines() if l.strip()]
    return [json.loads(l) for l in lines]


def test_stream_json_reply_joins_text_blocks(tmp_path, monkeypatch, clean_env):
    log_path = _install_recorder(tmp_path, monkeypatch, _stream(STREAM_EVENTS_OK), 0)

    response = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert field(response, "text") == "abcd"
    assert field(response, "model_call_error") is None

    calls = _read_calls(log_path)
    assert len(calls) >= 1
    argv = calls[-1]["argv"]
    assert "--output-format" in argv
    idx = argv.index("--output-format")
    assert idx + 1 < len(argv) and argv[idx + 1] == "stream-json"
    assert "--verbose" in argv


def test_stream_json_result_error_is_failure(tmp_path, monkeypatch, clean_env):
    log_path = _install_recorder(tmp_path, monkeypatch, _stream(STREAM_EVENTS_ERROR), 0)

    response = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert field(response, "text") is None
    assert field(response, "model_call_error") is not None
    assert len(_read_calls(log_path)) >= 1


def test_non_stream_stdout_is_reply_unchanged(tmp_path, monkeypatch, clean_env):
    log_path = _install_recorder(tmp_path, monkeypatch, "hello\n", 0)

    response = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert field(response, "text") == "hello\n"
    assert field(response, "model_call_error") is None
    assert len(_read_calls(log_path)) >= 1