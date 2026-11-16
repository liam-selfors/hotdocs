import json
import os
import stat
import sys

import pytest

import llm_tool_endpoint


MODEL = "claude-cli:claude-opus-5-5"

WRITE_FILE_TOOL = {
    "name": "write_file",
    "description": "Write a file in the working tree.",
    "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_fake(path, header_lines, body):
    content = "#!" + sys.executable + "\n" + "\n".join(header_lines) + "\n" + body
    path.write_text(content, encoding="utf-8")
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH | stat.S_IRUSR)
    return str(path)


_WATCHDOG = '''
import json, os, subprocess, sys, threading

_t = threading.Timer(120, lambda: os._exit(3))
_t.daemon = True
_t.start()
'''


_FULL_BODY = _WATCHDOG + '''
with open(ARGV_LOG, "w", encoding="utf-8") as fh:
    json.dump(sys.argv, fh)

argv = sys.argv
cfg_path = argv[argv.index("--mcp-config") + 1]
with open(cfg_path, encoding="utf-8") as fh:
    cfg = json.load(fh)
server = cfg["mcpServers"]["hotdocs"]
proc = subprocess.Popen(
    [server["command"]] + list(server["args"]),
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,
)


def send(msg):
    proc.stdin.write((json.dumps(msg) + "\\n").encode("utf-8"))
    proc.stdin.flush()


def wait_reply(req_id):
    while True:
        line = proc.stdout.readline()
        if not line:
            return None
        try:
            msg = json.loads(line.decode("utf-8"))
        except ValueError:
            continue
        if isinstance(msg, dict) and msg.get("id") == req_id:
            return msg


send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
      "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                 "clientInfo": {"name": "fake-claude", "version": "0"}}})
wait_reply(1)
send({"jsonrpc": "2.0", "method": "notifications/initialized"})
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
wait_reply(2)
send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
      "params": {"name": "write_file", "arguments": {"path": "a.py"}}})
reply = wait_reply(3)
with open(REPLY_LOG, "w", encoding="utf-8") as fh:
    json.dump(reply, fh)

try:
    proc.stdin.close()
except Exception:
    pass
try:
    proc.wait(timeout=15)
except subprocess.TimeoutExpired:
    proc.kill()
    proc.wait()

print(json.dumps({"type": "system", "subtype": "init"}), flush=True)
print(json.dumps({"type": "assistant", "message": {"role": "assistant",
      "content": [{"type": "text", "text": "all done"}]}}), flush=True)
print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                  "result": "all done", "num_turns": 3}), flush=True)
sys.exit(0)
'''


_MAX_TURNS_BODY = _WATCHDOG + '''
print(json.dumps({"type": "system", "subtype": "init"}), flush=True)
print(json.dumps({"type": "result", "subtype": "error_max_turns", "is_error": True,
                  "num_turns": 40}), flush=True)
sys.exit(0)
'''


_FAIL_BODY = _WATCHDOG + '''
sys.stderr.write("boom\\n")
sys.exit(1)
'''


@pytest.fixture
def loop_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    return bin_dir, logs


def _next_after(argv, flag):
    assert flag in argv, f"{flag!r} missing from argv {argv!r}"
    idx = argv.index(flag)
    assert idx + 1 < len(argv), f"{flag!r} has no value in argv {argv!r}"
    return argv[idx + 1]


def test_ac_tool_007_successful_cli_loop(loop_env):
    bin_dir, logs = loop_env
    argv_log = logs / "argv.json"
    reply_log = logs / "reply.json"
    fake = _write_fake(
        bin_dir / "fake_claude",
        ["ARGV_LOG = " + repr(str(argv_log)), "REPLY_LOG = " + repr(str(reply_log))],
        _FULL_BODY,
    )

    calls = []

    def execute(name, arguments):
        calls.append((name, arguments))
        return ("wrote a.py", False)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", MODEL, [WRITE_FILE_TOOL], execute, claude_command=fake
    )

    assert calls == [("write_file", {"path": "a.py"})]

    assert reply_log.exists(), "fake claude never recorded the tools/call reply"
    reply = json.loads(reply_log.read_text(encoding="utf-8"))
    assert reply is not None, "MCP server gave no reply to tools/call"
    assert reply["result"] == {
        "content": [{"type": "text", "text": "wrote a.py"}],
        "isError": False,
    }

    assert argv_log.exists(), "fake claude was never run"
    argv = json.loads(argv_log.read_text(encoding="utf-8"))
    assert _next_after(argv, "--tools") == ""
    assert "--strict-mcp-config" in argv
    assert _next_after(argv, "--setting-sources") == ""
    assert "--disable-slash-commands" in argv
    assert _next_after(argv, "--allowedTools") == "mcp__hotdocs__write_file"
    assert _next_after(argv, "--max-turns") == "40"
    assert "--safe-mode" not in argv

    assert field(result, "text") == "all done"
    assert field(result, "turns") == 3
    assert field(result, "tool_calls") == 1
    assert field(result, "stop") == "end_turn"


def test_ac_tool_007_error_max_turns_is_budget_exhausted(loop_env):
    bin_dir, _logs = loop_env
    fake = _write_fake(bin_dir / "fake_claude_max_turns", [], _MAX_TURNS_BODY)

    def execute(name, arguments):
        return ("unused", False)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", MODEL, [WRITE_FILE_TOOL], execute, claude_command=fake
    )

    assert field(result, "stop") == "budget_exhausted"


def test_ac_tool_007_nonzero_exit_without_result_is_network_error(loop_env):
    bin_dir, _logs = loop_env
    fake = _write_fake(bin_dir / "fake_claude_fail", [], _FAIL_BODY)

    def execute(name, arguments):
        return ("unused", False)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", MODEL, [WRITE_FILE_TOOL], execute, claude_command=fake
    )

    assert field(result, "stop") == "error"
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "network"