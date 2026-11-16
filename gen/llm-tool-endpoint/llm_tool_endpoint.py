"""Multi-turn tool-use loop over the providers that support tools.

The caller supplies the tools and one ``execute(name, arguments)`` function;
this module owns the wire formats, the loop and its budgets.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

_ANTHROPIC_MAX_TOKENS = 32000
_OPENAI_MAX_TOKENS = 32000

_ANTHROPIC_ACTIONS = {
    "tool_use": "tools",
    "end_turn": "end_turn",
    "stop_sequence": "end_turn",
    "pause_turn": "continue",
    "max_tokens": "truncated",
    "refusal": "refusal",
}

_OPENAI_ACTIONS = {
    "tool_calls": "tools",
    "stop": "end_turn",
    "length": "truncated",
    "content_filter": "refusal",
}

_MESSAGES = {
    "auth": "authentication failed",
    "rate_limit": "rate limited by provider",
    "timeout": "request timed out",
    "network": "request failed",
}

_CLAUDE_SETTINGS = '{"autoMemoryEnabled":false,"disableAllHooks":true}'


class ToolUseUnsupported(Exception):
    """Raised when the resolved provider does not support tool use."""


@dataclass
class ToolLoopResult:
    text: str
    transcript: list
    turns: int
    tool_calls: int
    stop: str
    model_call_error: dict | None

    def to_dict(self) -> dict:
        return asdict(self)


def _field(obj, key):
    return obj[key] if isinstance(obj, dict) else getattr(obj, key)


def _error(category: str) -> dict:
    return {"category": category, "message": _MESSAGES[category]}


def _load_llm_endpoint(repo_root):
    base = Path(repo_root, "gen", "llm-endpoint") if repo_root is not None else None
    if base is None or not base.is_dir():
        gen_dir = next(p for p in Path(__file__).resolve().parents if p.name == "gen")
        base = gen_dir.parent / "gen" / "llm-endpoint"
    spec = importlib.util.spec_from_file_location("llm_endpoint", base / "llm_endpoint.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["llm_endpoint"] = module
    spec.loader.exec_module(module)
    return module


def _loads_or_none(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


class _Calls:
    """Applies R-TOOL-004 and the tool-call cap to every call."""

    def __init__(self, tools, execute, max_tool_calls):
        self.names = {tool["name"] for tool in tools}
        self.execute = execute
        self.max_tool_calls = max_tool_calls
        self.count = 0
        self.over_cap = False

    def run(self, name, arguments):
        """Return ``(text, is_error)``, or ``None`` for a call past the cap."""
        if name not in self.names:
            return f"unknown tool: {name}", True
        if not isinstance(arguments, dict):
            return "arguments must be a JSON object", True
        if self.count >= self.max_tool_calls:
            self.over_cap = True
            return None
        self.count += 1
        try:
            text, is_error = self.execute(name, arguments)
        except Exception as exc:
            return f"tool error: {type(exc).__name__}: {exc}", True
        return text, is_error


def _status_category(code: int) -> str:
    if code in (401, 403):
        return "auth"
    if code == 429:
        return "rate_limit"
    if code in (408, 504):
        return "timeout"
    return "network"


def _post(url, headers, body, timeout):
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            return reply.read(), None
    except urllib.error.HTTPError as exc:
        return None, _error(_status_category(exc.code))
    except urllib.error.URLError as exc:
        timed_out = isinstance(exc.reason, (socket.timeout, TimeoutError))
        return None, _error("timeout" if timed_out else "network")
    except (socket.timeout, TimeoutError):
        return None, _error("timeout")
    except OSError:
        return None, _error("network")


def _parse_anthropic(raw):
    data = json.loads(raw.decode("utf-8"))
    content = data["content"]
    action = _ANTHROPIC_ACTIONS[data["stop_reason"]]
    text = "".join(block["text"] for block in content if block["type"] == "text")
    pending = (
        [(b["id"], b["name"], b["input"]) for b in content if b["type"] == "tool_use"]
        if action == "tools"
        else []
    )
    return {"role": "assistant", "content": content}, action, text, pending


def _anthropic_results(outcomes):
    blocks = []
    for call_id, text, is_error in outcomes:
        block = {"type": "tool_result", "tool_use_id": call_id, "content": text}
        if is_error:
            block["is_error"] = True
        blocks.append(block)
    return [{"role": "user", "content": blocks}]


def _parse_openai(raw):
    data = json.loads(raw.decode("utf-8"))
    choice = data["choices"][0]
    message = choice["message"]
    action = _OPENAI_ACTIONS[choice["finish_reason"]]
    text = message.get("content") or ""
    pending = (
        [
            (c["id"], c["function"]["name"], _loads_or_none(c["function"]["arguments"]))
            for c in message["tool_calls"]
        ]
        if action == "tools"
        else []
    )
    return message, action, text, pending


def _openai_results(outcomes):
    return [
        {"role": "tool", "tool_call_id": call_id, "content": text}
        for call_id, text, _is_error in outcomes
    ]


def _http_loop(provider, resolved, key, system, prompt, tools, calls, max_turns, wall_seconds):
    base = _field(resolved, "base_url")
    model_name = _field(resolved, "model")
    timeout_seconds = _field(resolved, "timeout_seconds")
    if provider == "anthropic":
        url = f"{base}/v1/messages"
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        fixed = {
            "model": model_name,
            "max_tokens": _ANTHROPIC_MAX_TOKENS,
            "system": [
                {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
            ],
            "tools": [
                {
                    "name": t["name"],
                    "description": t["description"],
                    "input_schema": t["input_schema"],
                }
                for t in tools
            ],
            "tool_choice": {"type": "auto"},
        }
        messages = [{"role": "user", "content": prompt}]
        parse, results = _parse_anthropic, _anthropic_results
    else:
        url = f"{base}/chat/completions"
        headers = {"content-type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        token_key = "max_completion_tokens" if provider == "openai" else "max_tokens"
        fixed = {
            "model": model_name,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t["description"],
                        "parameters": t["input_schema"],
                    },
                }
                for t in tools
            ],
            "tool_choice": "auto",
            token_key: _OPENAI_MAX_TOKENS,
        }
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        parse, results = _parse_openai, _openai_results

    deadline = time.monotonic() + wall_seconds
    turns = 0
    text = ""
    transcript = messages
    while True:
        remaining = deadline - time.monotonic()
        if turns >= max_turns or remaining <= 0:
            return ToolLoopResult(text, transcript, turns, calls.count, "budget_exhausted", None)
        transcript = messages
        turns += 1
        raw, error = _post(url, headers, dict(fixed, messages=messages),
                           min(timeout_seconds, remaining))
        if error is not None:
            return ToolLoopResult(text, transcript, turns, calls.count, "error", error)
        try:
            assistant, action, text, pending = parse(raw)
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            return ToolLoopResult(text, transcript, turns, calls.count, "error",
                                  {"category": "network", "message": "invalid reply from provider"})
        transcript = messages + [assistant]
        if action == "continue":
            messages = transcript
            continue
        if action != "tools":
            return ToolLoopResult(text, transcript, turns, calls.count, action, None)
        outcomes = []
        for call_id, name, arguments in pending:
            outcome = calls.run(name, arguments)
            if outcome is None:
                return ToolLoopResult(text, transcript, turns, calls.count,
                                      "budget_exhausted", None)
            outcomes.append((call_id, outcome[0], outcome[1]))
        messages = transcript + results(outcomes)


def _answer_calls(server, calls, stop_event):
    while not stop_event.is_set():
        try:
            conn, _ = server.accept()
        except socket.timeout:
            continue
        with conn, conn.makefile("rb") as reader:
            request = json.loads(reader.readline())
            outcome = calls.run(request["name"], request["arguments"])
            text, is_error = (
                outcome if outcome is not None else ("tool-call budget exhausted", True)
            )
            line = json.dumps({"text": text, "is_error": is_error}) + "\n"
            conn.sendall(line.encode("utf-8"))


def _claude_cli_loop(resolved, system, prompt, tools, calls, max_turns, wall_seconds,
                     claude_command):
    workdir = tempfile.mkdtemp()
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        tools_path = os.path.join(workdir, "tools.json")
        with open(tools_path, "w", encoding="utf-8") as fh:
            json.dump(tools, fh)
        socket_path = os.path.join(workdir, "mcp.sock")
        server.bind(socket_path)
        server.listen()
        server.settimeout(0.05)
        config_path = os.path.join(workdir, "mcp.json")
        config = {
            "mcpServers": {
                "hotdocs": {
                    "command": sys.executable,
                    "args": [os.path.abspath(__file__), "--mcp-serve", socket_path, tools_path],
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as fh:
            json.dump(config, fh)
        command = [
            claude_command, "-p",
            "--model", _field(resolved, "model"),
            "--output-format", "stream-json", "--verbose",
            "--tools", "",
            "--mcp-config", config_path, "--strict-mcp-config",
            "--allowedTools", *[f"mcp__hotdocs__{t['name']}" for t in tools],
            "--no-session-persistence",
            "--setting-sources", "",
            "--disable-slash-commands",
            "--settings", _CLAUDE_SETTINGS,
            "--system-prompt", system,
            "--max-turns", str(max_turns),
        ]
        stop_event = threading.Event()
        thread = threading.Thread(target=_answer_calls, args=(server, calls, stop_event),
                                  daemon=True)
        thread.start()
        try:
            proc = subprocess.Popen(
                command, cwd=workdir, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, start_new_session=True,
                text=True, encoding="utf-8",
            )
            killed = False
            try:
                out, _ = proc.communicate(prompt, timeout=wall_seconds)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                out, _ = proc.communicate()
                killed = True
        finally:
            stop_event.set()
            thread.join()
    finally:
        server.close()
        shutil.rmtree(workdir, ignore_errors=True)

    events = []
    for line in out.splitlines():
        event = _loads_or_none(line)
        if isinstance(event, dict):
            events.append(event)
    results = [e for e in events if e.get("type") == "result"]
    result = results[-1] if results else {}
    text = result.get("result") or ""
    turns = result.get("num_turns", 0)
    if calls.over_cap or killed or result.get("subtype") == "error_max_turns":
        return ToolLoopResult(text, events, turns, calls.count, "budget_exhausted", None)
    if proc.returncode != 0 or not results:
        return ToolLoopResult(text, events, turns, calls.count, "error",
                              {"category": "network", "message": "claude command failed"})
    return ToolLoopResult(text, events, turns, calls.count, "end_turn", None)


def run_tool_loop(system: str, prompt: str, model: str, tools: list, execute, *,
                  max_turns: int = 40, max_tool_calls: int = 120,
                  wall_seconds: float = 1800.0, repo_root: Path = None,
                  claude_command: str = "claude") -> ToolLoopResult:
    endpoint = _load_llm_endpoint(repo_root)
    resolved = endpoint.resolve_provider(model, endpoint.load_config())
    provider = _field(resolved, "provider")
    if provider in ("gemini", "ollama"):
        raise ToolUseUnsupported(f"tool use is not supported by provider {provider}")
    calls = _Calls(tools, execute, max_tool_calls)
    if provider == "claude-cli":
        return _claude_cli_loop(resolved, system, prompt, tools, calls, max_turns,
                                wall_seconds, claude_command)
    key_env = _field(resolved, "api_key_env")
    key = os.environ.get(key_env) if key_env else None
    if provider != "openai-compatible" and not key:
        return ToolLoopResult("", [], 0, 0, "error",
                              {"category": "auth", "message": "API key not set"})
    return _http_loop(provider, resolved, key, system, prompt, tools, calls, max_turns,
                      wall_seconds)


def _forward_call(socket_path, params):
    request = {"name": params["name"], "arguments": params.get("arguments", {})}
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conn:
        conn.connect(socket_path)
        conn.sendall((json.dumps(request) + "\n").encode("utf-8"))
        with conn.makefile("rb") as reader:
            answer = json.loads(reader.readline())
    return {"content": [{"type": "text", "text": answer["text"]}],
            "isError": answer["is_error"]}


def serve_mcp(socket_path: str, tools_path: str) -> int:
    with open(tools_path, encoding="utf-8") as fh:
        tools = json.load(fh)
    for line in sys.stdin:
        message = json.loads(line)
        if "id" not in message:
            continue
        method = message.get("method")
        reply = {"jsonrpc": "2.0", "id": message["id"]}
        if method == "initialize":
            reply["result"] = {
                "protocolVersion": message["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "hotdocs", "version": "1"},
            }
        elif method == "tools/list":
            reply["result"] = {
                "tools": [
                    {
                        "name": t["name"],
                        "description": t["description"],
                        "inputSchema": t["input_schema"],
                    }
                    for t in tools
                ]
            }
        elif method == "tools/call":
            reply["result"] = _forward_call(socket_path, message["params"])
        else:
            reply["error"] = {"code": -32601, "message": "Method not found"}
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.stdin.reconfigure(encoding="utf-8")
    sys.exit(serve_mcp(sys.argv[2], sys.argv[3]))
