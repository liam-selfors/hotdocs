import json
import os
import sys

import pytest

import llm_endpoint


pytestmark = pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="recorder relies on an executable shebang script on PATH",
)


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _setup(tmp_path, monkeypatch, stdout_text, exit_code=0):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    log_path = tmp_path / "claude_invocations.log"

    script = (
        "#!" + sys.executable + "\n"
        "import sys, json\n"
        "with open(" + repr(str(log_path)) + ", 'a') as _f:\n"
        "    _f.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "sys.stdout.write(" + repr(stdout_text) + ")\n"
        "sys.stdout.flush()\n"
        "sys.exit(" + repr(int(exit_code)) + ")\n"
    )
    claude_path = bin_dir / "claude"
    claude_path.write_text(script)
    os.chmod(str(claude_path), 0o755)

    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.chdir(work_dir)
    return log_path


def _read_invocations(log_path):
    assert log_path.exists(), "the claude recorder was never invoked"
    lines = [ln for ln in log_path.read_text().splitlines() if ln.strip()]
    assert lines, "the claude recorder was never invoked"
    return [json.loads(ln) for ln in lines]


def _has_stream_json(argv):
    has_format = False
    for i, arg in enumerate(argv):
        if arg == "--output-format" and i + 1 < len(argv) and argv[i + 1] == "stream-json":
            has_format = True
        if arg == "--output-format=stream-json":
            has_format = True
    return has_format and "--verbose" in argv


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


def test_stream_json_reply_joins_every_assistant_text_block(tmp_path, monkeypatch):
    log_path = _setup(tmp_path, monkeypatch, _stream_output(False))

    result = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert _field(result, "text") == "abcd"
    assert _field(result, "model_call_error") is None

    invocations = _read_invocations(log_path)
    for argv in invocations:
        assert _has_stream_json(argv), (
            "recorded command lacks --output-format stream-json --verbose: %r" % (argv,)
        )


def test_result_line_with_is_error_true_is_a_failure(tmp_path, monkeypatch):
    log_path = _setup(tmp_path, monkeypatch, _stream_output(True))

    result = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert _field(result, "text") is None
    assert _field(result, "model_call_error") is not None
    _read_invocations(log_path)


def test_non_stream_output_is_the_reply_unchanged(tmp_path, monkeypatch):
    log_path = _setup(tmp_path, monkeypatch, "hello\n")

    result = llm_endpoint.complete("hi", "claude-sonnet-5")

    assert _field(result, "text") == "hello\n"
    assert _field(result, "model_call_error") is None
    _read_invocations(log_path)