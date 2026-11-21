# hotdocs-criterion: sha256:3956a844443f8e999a86db1ade33aee56f121419aa9a1d21f1802040981745a3
import json
import os
import stat
import sys

import pytest

import llm_tool_endpoint


MODEL = "claude-cli:claude-opus-5-5"

WRITE_FILE_TOOL = {
    "name": "write_file",
    "description": "Write a file to the workspace.",
    "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string"}},
        "required": ["path"],
    },
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def has_pair(argv, flag, value):
    for i in range(len(argv) - 1):
        if argv[i] == flag and argv[i + 1] == value:
            return True
    return False


def write_executable(path, body):
    source = "#!" + sys.executable + "\n" + body
    path.write_text(source, encoding="utf-8")
    mode = os.stat(str(path)).st_mode
    os.chmod(str(path), mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return str(path)


@pytest.fixture
def loop_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    return scripts


def full_fake_body(argv_file, reply_file):
    return (
        "import json\n"
        "import subprocess\n"
        "import sys\n"
        "\n"
        "ARGV_FILE = " + repr(argv_file) + "\n"
        "REPLY_FILE = " + repr(reply_file) + "\n"
        "\n"
        "argv = sys.argv[1:]\n"
        "with open(ARGV_FILE, 'w', encoding='utf-8') as fh:\n"
        "    json.dump(argv, fh)\n"
        "\n"
        "try:\n"
        "    sys.stdin.read()\n"
        "except Exception:\n"
        "    pass\n"
        "\n"
        "cfg_path = argv[argv.index('--mcp-config') + 1]\n"
        "with open(cfg_path, encoding='utf-8') as fh:\n"
        "    cfg = json.load(fh)\n"
        "server = cfg['mcpServers']['hotdocs']\n"
        "proc = subprocess.Popen([server['command']] + list(server['args']),\n"
        "                        stdin=subprocess.PIPE, stdout=subprocess.PIPE)\n"
        "\n"
        "def send(msg):\n"
        "    proc.stdin.write((json.dumps(msg) + '\\n').encode('utf-8'))\n"
        "    proc.stdin.flush()\n"
        "\n"
        "def read_reply(want_id):\n"
        "    while True:\n"
        "        line = proc.stdout.readline()\n"
        "        if not line:\n"
        "            return None\n"
        "        text = line.decode('utf-8').strip()\n"
        "        if not text:\n"
        "            continue\n"
        "        try:\n"
        "            msg = json.loads(text)\n"
        "        except ValueError:\n"
        "            continue\n"
        "        if isinstance(msg, dict) and msg.get('id') == want_id:\n"
        "            return text\n"
        "\n"
        "send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',\n"
        "      'params': {'protocolVersion': '2024-11-05', 'capabilities': {},\n"
        "                 'clientInfo': {'name': 'fake-claude', 'version': '0'}}})\n"
        "read_reply(1)\n"
        "send({'jsonrpc': '2.0', 'method': 'notifications/initialized'})\n"
        "send({'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list', 'params': {}})\n"
        "read_reply(2)\n"
        "send({'jsonrpc': '2.0', 'id': 3, 'method': 'tools/call',\n"
        "      'params': {'name': 'write_file', 'arguments': {'path': 'a.py'}}})\n"
        "reply = read_reply(3)\n"
        "with open(REPLY_FILE, 'w', encoding='utf-8') as fh:\n"
        "    fh.write(reply if reply is not None else '')\n"
        "\n"
        "try:\n"
        "    proc.stdin.close()\n"
        "except Exception:\n"
        "    pass\n"
        "try:\n"
        "    proc.wait(timeout=10)\n"
        "except Exception:\n"
        "    proc.kill()\n"
        "\n"
        "print(json.dumps({'type': 'system', 'subtype': 'init'}))\n"
        "print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': False,\n"
        "                  'result': 'all done', 'num_turns': 3}))\n"
        "sys.stdout.flush()\n"
        "sys.exit(0)\n"
    )


def test_claude_cli_tool_call_round_trip_and_flags(loop_env):
    argv_file = str(loop_env / "argv.json")
    reply_file = str(loop_env / "reply.json")
    fake = write_executable(loop_env / "fake_claude", full_fake_body(argv_file, reply_file))

    calls = []

    def execute(name, arguments):
        calls.append((name, arguments))
        return ("wrote a.py", False)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", MODEL, [WRITE_FILE_TOOL], execute, claude_command=fake
    )

    assert calls == [("write_file", {"path": "a.py"})]

    with open(reply_file, encoding="utf-8") as fh:
        reply_text = fh.read()
    assert reply_text.strip(), "fake claude recorded no tools/call reply"
    reply = json.loads(reply_text)
    assert reply["result"] == {
        "content": [{"type": "text", "text": "wrote a.py"}],
        "isError": False,
    }

    with open(argv_file, encoding="utf-8") as fh:
        argv = json.load(fh)
    assert has_pair(argv, "--tools", "")
    assert "--strict-mcp-config" in argv
    assert has_pair(argv, "--setting-sources", "")
    assert "--disable-slash-commands" in argv
    assert has_pair(argv, "--allowedTools", "mcp__hotdocs__write_file")
    assert has_pair(argv, "--max-turns", "40")
    assert "--safe-mode" not in argv

    assert field(result, "text") == "all done"
    assert field(result, "turns") == 3
    assert field(result, "tool_calls") == 1
    assert field(result, "stop") == "end_turn"


def test_claude_cli_error_max_turns_is_budget_exhausted(loop_env):
    body = (
        "import json\n"
        "import sys\n"
        "try:\n"
        "    sys.stdin.read()\n"
        "except Exception:\n"
        "    pass\n"
        "print(json.dumps({'type': 'result', 'subtype': 'error_max_turns',\n"
        "                  'is_error': True, 'num_turns': 40}))\n"
        "sys.stdout.flush()\n"
        "sys.exit(0)\n"
    )
    fake = write_executable(loop_env / "fake_claude_max", body)

    def execute(name, arguments):
        return ("unused", False)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", MODEL, [WRITE_FILE_TOOL], execute, claude_command=fake
    )

    assert field(result, "stop") == "budget_exhausted"


def test_claude_cli_nonzero_exit_without_result_is_network_error(loop_env):
    body = (
        "import sys\n"
        "try:\n"
        "    sys.stdin.read()\n"
        "except Exception:\n"
        "    pass\n"
        "sys.stderr.write('boom\\n')\n"
        "sys.exit(1)\n"
    )
    fake = write_executable(loop_env / "fake_claude_fail", body)

    def execute(name, arguments):
        return ("unused", False)

    result = llm_tool_endpoint.run_tool_loop(
        "sys", "go", MODEL, [WRITE_FILE_TOOL], execute, claude_command=fake
    )

    assert field(result, "stop") == "error"
    error = field(result, "model_call_error")
    assert error is not None
    assert field(error, "category") == "network"