# hotdocs-criterion: sha256:83b6540fcdf9d87f23fbe555fb53bf44c0da16ea7be30c410d7f3e5cefc4a326
import json
import os
import stat
import sys
from pathlib import Path

import pytest

import llm_tool_endpoint


MODEL = "claude-cli:claude-opus-5-5"

WRITE_FILE_TOOL = {
    "name": "write_file",
    "description": "Write a file.",
    "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@pytest.fixture
def clean_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return tmp_path


def _write_executable(path, source):
    path.write_text(source, encoding="utf-8")
    mode = os.stat(str(path)).st_mode
    os.chmod(str(path), mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


_TOOL_CALL_BODY = r'''
signal.alarm(120)

with open(ARGV_PATH, "w", encoding="utf-8") as f:
    json.dump(sys.argv, f)

try:
    sys.stdin.read()
except Exception:
    pass

argv = sys.argv
cfg_path = argv[argv.index("--mcp-config") + 1]
with open(cfg_path, encoding="utf-8") as f:
    cfg = json.load(f)
server = cfg["mcpServers"]["hotdocs"]
proc = subprocess.Popen(
    [server["command"]] + list(server["args"]),
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
)


def send(msg):
    proc.stdin.write((json.dumps(msg) + "\n").encode("utf-8"))
    proc.stdin.flush()


def await_reply(req_id):
    while True:
        raw = proc.stdout.readline()
        if not raw:
            sys.stderr.write("fake claude: server closed stdout\n")
            sys.exit(1)
        line = raw.decode("utf-8").strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            continue
        if isinstance(msg, dict) and msg.get("id") == req_id and ("result" in msg or "error" in msg):
            return line


send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
      "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                 "clientInfo": {"name": "fake-claude", "version": "0"}}})
await_reply(1)
send({"jsonrpc": "2.0", "method": "notifications/initialized"})
send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
await_reply(2)
send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
      "params": {"name": "write_file", "arguments": {"path": "a.py"}}})
reply_line = await_reply(3)
with open(REPLY_PATH, "w", encoding="utf-8") as f:
    f.write(reply_line + "\n")

try:
    proc.stdin.close()
except Exception:
    pass
try:
    proc.wait(timeout=10)
except Exception:
    proc.kill()
    proc.wait()

print(json.dumps({"type": "system", "subtype": "init"}))
print(json.dumps({"type": "assistant", "message": {"role": "assistant",
      "content": [{"type": "text", "text": "all done"}]}}))
print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                  "result": "all done", "num_turns": 3}))
sys.stdout.flush()
sys.exit(0)
'''


def _tool_call_fake(path, argv_path, reply_path):
    source = (
        "#!" + sys.executable + "\n"
        "import json\n"
        "import os\n"
        "import signal\n"
        "import subprocess\n"
        "import sys\n"
        "ARGV_PATH = " + repr(str(argv_path)) + "\n"
        "REPLY_PATH = " + repr(str(reply_path)) + "\n"
        + _TOOL_CALL_BODY
    )
    return _write_executable(path, source)


_MAX_TURNS_BODY = r'''
try:
    sys.stdin.read()
except Exception:
    pass
print(json.dumps({"type": "system", "subtype": "init"}))
print(json.dumps({"type": "result", "subtype": "error_max_turns", "is_error": True,
                  "result": "", "num_turns": 40}))
sys.stdout.flush()
sys.exit(0)
'''

_EXIT_ONE_BODY = r'''
try:
    sys.stdin.read()
except Exception:
    pass
print(json.dumps({"type": "system", "subtype": "init"}))
sys.stdout.flush()
sys.exit(1)
'''


def _simple_fake(path, body):
    source = (
        "#!" + sys.executable + "\n"
        "import json\n"
        "import sys\n"
        + body
    )
    return _write_executable(path, source)


def test_claude_cli_tool_call_argv_and_result(clean_env):
    tmp = clean_env
    argv_path = tmp / "argv.json"
    reply_path = tmp / "reply.json"
    fake = _tool_call_fake(tmp / "fake_claude.py", argv_path, reply_path)

    calls = []

    def execute(name, arguments):
        calls.append((name, arguments))
        return ("wrote a.py", False)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", MODEL, [WRITE_FILE_TOOL], execute,
        claude_command=str(fake),
    )

    assert calls == [("write_file", {"path": "a.py"})]

    assert reply_path.is_file(), "fake claude never recorded the tools/call reply"
    reply = json.loads(reply_path.read_text(encoding="utf-8").strip())
    assert reply.get("id") == 3
    assert reply["result"] == {
        "content": [{"type": "text", "text": "wrote a.py"}],
        "isError": False,
    }

    argv = json.loads(argv_path.read_text(encoding="utf-8"))
    args = argv[1:]

    def value_after(flag):
        assert flag in args, flag + " missing from argv: " + repr(args)
        i = args.index(flag)
        assert i + 1 < len(args), flag + " has no value"
        return args[i + 1]

    assert value_after("--tools") == ""
    assert "--strict-mcp-config" in args
    assert value_after("--setting-sources") == ""
    assert "--disable-slash-commands" in args
    assert value_after("--allowedTools") == "mcp__hotdocs__write_file"
    assert value_after("--max-turns") == "40"
    assert "--safe-mode" not in args

    assert field(result, "text") == "all done"
    assert field(result, "turns") == 3
    assert field(result, "tool_calls") == 1
    assert field(result, "stop") == "end_turn"
    assert field(result, "model_call_error") is None


def test_claude_cli_error_max_turns_is_budget_exhausted(clean_env):
    tmp = clean_env
    fake = _simple_fake(tmp / "fake_claude_max.py", _MAX_TURNS_BODY)

    def execute(name, arguments):
        return ("unused", False)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", MODEL, [WRITE_FILE_TOOL], execute,
        claude_command=str(fake),
    )

    assert field(result, "stop") == "budget_exhausted"


def test_claude_cli_exit_one_without_result_is_network_error(clean_env):
    tmp = clean_env
    fake = _simple_fake(tmp / "fake_claude_fail.py", _EXIT_ONE_BODY)

    def execute(name, arguments):
        return ("unused", False)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", MODEL, [WRITE_FILE_TOOL], execute,
        claude_command=str(fake),
    )

    assert field(result, "stop") == "error"
    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "network"