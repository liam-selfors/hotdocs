# hotdocs-criterion: sha256:8aae07b0e59757f3401b07913118bbbb40cda719e74c359b146a05d105302854
import json
import os
import stat
import sys

import pytest

import llm_endpoint


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


STREAM_LINES = [
    {"type": "system"},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": "ab"}]}},
    {
        "type": "assistant",
        "message": {"content": [{"type": "thinking"}, {"type": "text", "text": "cd"}]},
    },
]


def _stream_output(is_error):
    lines = list(STREAM_LINES) + [{"type": "result", "is_error": is_error}]
    return "".join(json.dumps(line) + "\n" for line in lines)


def _install_recorder(tmp_path, monkeypatch, stdout_text, exit_code=0):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "claude_calls.log"
    script = (
        "#!" + sys.executable + "\n"
        "import json\n"
        "import os\n"
        "import sys\n"
        "with open(" + repr(str(log_path)) + ", 'a') as f:\n"
        "    f.write(json.dumps({'argv': sys.argv[1:], "
        "'key': os.environ.get('ANTHROPIC_API_KEY')}) + '\\n')\n"
        "try:\n"
        "    sys.stdin.read()\n"
        "except Exception:\n"
        "    pass\n"
        "sys.stdout.write(" + repr(stdout_text) + ")\n"
        "sys.stdout.flush()\n"
        "sys.exit(" + repr(exit_code) + ")\n"
    )
    claude_path = bin_dir / "claude"
    claude_path.write_text(script)
    claude_path.chmod(
        claude_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    return log_path


def _read_calls(log_path):
    assert log_path.is_file(), "the claude recorder was never run"
    return [
        json.loads(line)
        for line in log_path.read_text().splitlines()
        if line.strip()
    ]


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return tmp_path


def test_stream_text_blocks_are_joined_and_flags_recorded(workdir, monkeypatch):
    log_path = _install_recorder(workdir, monkeypatch, _stream_output(False))

    response = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert field(response, "text") == "abcd"
    assert field(response, "model_call_error") is None

    calls = _read_calls(log_path)
    assert len(calls) == 1
    argv = calls[0]["argv"]
    assert "--output-format" in argv
    idx = argv.index("--output-format")
    assert idx + 1 < len(argv)
    assert argv[idx + 1] == "stream-json"
    assert "--verbose" in argv


def test_result_is_error_true_is_a_failure(workdir, monkeypatch):
    log_path = _install_recorder(workdir, monkeypatch, _stream_output(True))

    response = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert field(response, "text") is None
    error = field(response, "model_call_error")
    assert error is not None
    assert field(error, "category") in ("network", "auth", "rate_limit", "timeout")
    assert len(_read_calls(log_path)) == 1


def test_non_stream_stdout_with_zero_exit_is_whole_reply(workdir, monkeypatch):
    log_path = _install_recorder(workdir, monkeypatch, "hello\n")

    response = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert field(response, "text") == "hello\n"
    assert field(response, "model_call_error") is None
    assert len(_read_calls(log_path)) == 1