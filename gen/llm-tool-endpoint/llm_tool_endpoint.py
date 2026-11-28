"""LLM Tool Endpoint: a multi-turn tool-use loop over any tool-capable provider."""

import http.client
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
from dataclasses import dataclass, field
from pathlib import Path

_ERROR_MESSAGES = {
    "auth": "authentication failed",
    "rate_limit": "rate limited by backend",
    "timeout": "request timed out",
    "network": "request failed",
}

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

_CLAUDE_SETTINGS = '{"autoMemoryEnabled":false,"disableAllHooks":true}'


class ToolUseUnsupported(Exception):
    """Raised for a provider that does not support tool use."""


@dataclass
class ToolLoopResult:
    text: str = ""
    transcript: list = field(default_factory=list)
    turns: int = 0
    tool_calls: int = 0
    stop: str = "end_turn"
    model_call_error: dict = None

    def to_dict(self):
        return {
            "text": self.text,
            "transcript": self.transcript,
            "turns": self.turns,
            "tool_calls": self.tool_calls,
            "stop": self.stop,
            "model_call_error": self.model_call_error,
        }


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _error(category):
    return {"category": category, "message": _ERROR_MESSAGES[category]}


def _tool_root():
    for parent in Path(__file__).resolve().parents:
        if parent.name == "gen":
            return parent.parent
    return None


def _load_llm_endpoint(repo_root):
    rel = Path("gen", "llm-endpoint", "llm_endpoint.py")
    path = None
    if repo_root is not None:
        candidate = Path(repo_root) / rel
        if candidate.is_file():
            path = candidate
    if path is None:
        path = _tool_root() / rel
    spec = importlib.util.spec_from_file_location("llm_endpoint", str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["llm_endpoint"] = module
    spec.loader.exec_module(module)
    return module


class _Budget:
    """Tool-call counter and dispatcher shared by every loop."""

    def __init__(self, names, execute, cap):
        self.names = names
        self.execute = execute
        self.cap = cap
        self.count = 0
        self.exhausted = False
        self.lock = threading.Lock()

    def dispatch(self, name, arguments):
        """Return (text, is_error), or None when the call is past the cap."""
        if name not in self.names:
            return "unknown tool: %s" % name, True
        if not isinstance(arguments, dict):
            return "arguments must be a JSON object", True
        with self.lock:
            if self.count >= self.cap:
                return None
            self.count += 1
        try:
            text, is_error = self.execute(name, arguments)
        except Exception as exc:
            return "tool error: %s: %s" % (type(exc).__name__, exc), True
        return text, bool(is_error)


def _post(url, headers, body, timeout):
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as reply:
            raw = reply.read()
    except urllib.error.HTTPError as exc:
        code = exc.code
        if code in (401, 403):
            return None, _error("auth")
        if code == 429:
            return None, _error("rate_limit")
        if code in (408, 504):
            return None, _error("timeout")
        return None, _error("network")
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (socket.timeout, TimeoutError)):
            return None, _error("timeout")
        return None, _error("network")
    except (socket.timeout, TimeoutError):
        return None, _error("timeout")
    except (OSError, http.client.HTTPException):
        return None, _error("network")
    try:
        return json.loads(raw), None
    except ValueError:
        return None, _error("network")


# --- anthropic -------------------------------------------------------------

def _anthropic_body(model, system, tools):
    tool_list = [
        {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
        for t in tools
    ]

    def build(messages):
        return {
            "model": model,
            "max_tokens": 32000,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "tools": tool_list,
            "tool_choice": {"type": "auto"},
            "messages": messages,
        }

    return build


def _anthropic_parse(data):
    content = data["content"]
    action = _ANTHROPIC_ACTIONS[data["stop_reason"]]
    text = "".join(block["text"] for block in content if block["type"] == "text")
    calls = []
    if action == "tools":
        calls = [
            (block["id"], block["name"], block["input"])
            for block in content
            if block["type"] == "tool_use"
        ]
    return {"role": "assistant", "content": content}, text, action, calls


def _anthropic_results(results):
    blocks = []
    for call_id, (text, is_error) in results:
        block = {"type": "tool_result", "tool_use_id": call_id, "content": text}
        if is_error:
            block["is_error"] = True
        blocks.append(block)
    return [{"role": "user", "content": blocks}]


# --- openai / openai-compatible ---------------------------------------------

def _openai_body(model, tools, token_key):
    tool_list = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]

    def build(messages):
        return {
            "model": model,
            "messages": messages,
            "tools": tool_list,
            "tool_choice": "auto",
            token_key: 32000,
        }

    return build


def _openai_parse(data):
    choice = data["choices"][0]
    message = choice["message"]
    action = _OPENAI_ACTIONS[choice["finish_reason"]]
    text = message.get("content") or ""
    calls = []
    if action == "tools":
        for call in message["tool_calls"]:
            function = call["function"]
            try:
                arguments = json.loads(function["arguments"])
            except (ValueError, TypeError):
                arguments = None
            calls.append((call["id"], function["name"], arguments))
    return message, text, action, calls


def _openai_results(results):
    return [
        {"role": "tool", "tool_call_id": call_id, "content": text}
        for call_id, (text, _is_error) in results
    ]


# --- HTTP loop ---------------------------------------------------------------

def _http_loop(url, headers, build, parse, results_of, messages, timeout_seconds,
               budget, max_turns, wall_seconds):
    start = time.monotonic()
    transcript = messages
    turns = 0
    text = ""

    def finish(stop, error=None):
        return ToolLoopResult(text, transcript, turns, budget.count, stop, error)

    while True:
        remaining = wall_seconds - (time.monotonic() - start)
        if turns >= max_turns or remaining <= 0:
            return finish("budget_exhausted")
        data, error = _post(url, headers, build(messages), min(timeout_seconds, remaining))
        turns += 1
        transcript = messages
        if error is not None:
            return finish("error", error)
        try:
            assistant, reply_text, action, calls = parse(data)
        except (KeyError, IndexError, TypeError, AttributeError):
            return finish("error", _error("network"))
        text = reply_text
        transcript = messages + [assistant]
        if action == "continue":
            messages = transcript
            continue
        if action != "tools":
            return finish(action)
        results = []
        for call_id, name, arguments in calls:
            outcome = budget.dispatch(name, arguments)
            if outcome is None:
                return finish("budget_exhausted")
            results.append((call_id, outcome))
        messages = transcript + results_of(results)


# --- claude-cli loop -----------------------------------------------------------

def _answer_connection(conn, budget):
    with conn, conn.makefile("rwb") as stream:
        for line in stream:
            request = json.loads(line.decode("utf-8"))
            outcome = budget.dispatch(request.get("name"), request.get("arguments"))
            if outcome is None:
                budget.exhausted = True
                outcome = ("tool-call budget exhausted", True)
            reply = {"text": outcome[0], "is_error": outcome[1]}
            stream.write((json.dumps(reply) + "\n").encode("utf-8"))
            stream.flush()


def _accept_loop(server, budget, stopping):
    while not stopping.is_set():
        try:
            conn, _ = server.accept()
        except socket.timeout:
            continue
        except OSError:
            return
        conn.setblocking(True)
        threading.Thread(target=_answer_connection, args=(conn, budget), daemon=True).start()


def _claude_loop(claude_command, model, system, prompt, tools, budget, max_turns,
                 wall_seconds):
    workdir = tempfile.mkdtemp()
    server = None
    stopping = threading.Event()
    try:
        tools_path = os.path.join(workdir, "tools.json")
        with open(tools_path, "w", encoding="utf-8") as handle:
            json.dump(tools, handle)
        socket_path = os.path.join(workdir, "mcp.sock")
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(socket_path)
        server.listen()
        server.settimeout(0.1)
        config_path = os.path.join(workdir, "mcp.json")
        config = {
            "mcpServers": {
                "hotdocs": {
                    "command": sys.executable,
                    "args": [os.path.abspath(__file__), "--mcp-serve", socket_path, tools_path],
                }
            }
        }
        with open(config_path, "w", encoding="utf-8") as handle:
            json.dump(config, handle)
        threading.Thread(
            target=_accept_loop, args=(server, budget, stopping), daemon=True
        ).start()

        argv = [
            claude_command, "-p", "--model", model,
            "--output-format", "stream-json", "--verbose",
            "--tools", "", "--mcp-config", config_path, "--strict-mcp-config",
            "--allowedTools",
        ]
        argv += ["mcp__hotdocs__%s" % t["name"] for t in tools]
        argv += [
            "--no-session-persistence", "--setting-sources", "",
            "--disable-slash-commands", "--settings", _CLAUDE_SETTINGS,
            "--system-prompt", system, "--max-turns", str(max_turns),
        ]
        proc = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, cwd=workdir, text=True,
            encoding="utf-8", errors="replace", start_new_session=True,
        )
        killed = False
        try:
            out, _ = proc.communicate(prompt, timeout=wall_seconds)
        except subprocess.TimeoutExpired:
            killed = True
            os.killpg(proc.pid, signal.SIGKILL)
            out, _ = proc.communicate()
    finally:
        stopping.set()
        if server is not None:
            server.close()
        shutil.rmtree(workdir, ignore_errors=True)

    events = []
    result = None
    for line in out.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        events.append(event)
        if isinstance(event, dict) and event.get("type") == "result":
            result = event

    text = ""
    turns = 0
    subtype = None
    if result is not None:
        text = result.get("result") or ""
        turns = result.get("num_turns") or 0
        subtype = result.get("subtype")

    error = None
    if killed or budget.exhausted or subtype == "error_max_turns":
        stop = "budget_exhausted"
    elif proc.returncode != 0 or result is None:
        stop = "error"
        error = {"category": "network", "message": "claude-cli call failed"}
    else:
        stop = "end_turn"
    return ToolLoopResult(text, events, turns, budget.count, stop, error)


# --- public API ----------------------------------------------------------------

def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,
                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,
                  claude_command="claude"):
    llm = _load_llm_endpoint(repo_root)
    resolved = llm.resolve_provider(model, llm.load_config())
    provider = _get(resolved, "provider")
    if provider in ("gemini", "ollama"):
        raise ToolUseUnsupported("tool use is not supported by provider %s" % provider)

    model_name = _get(resolved, "model")
    budget = _Budget({t["name"] for t in tools}, execute, max_tool_calls)

    if provider == "claude-cli":
        return _claude_loop(claude_command, model_name, system, prompt, tools, budget,
                            max_turns, wall_seconds)

    key_env = _get(resolved, "api_key_env")
    key = os.environ.get(key_env) if key_env else None
    if not key and provider in ("anthropic", "openai"):
        return ToolLoopResult("", [], 0, 0, "error",
                              {"category": "auth", "message": "no API key configured"})

    base = _get(resolved, "base_url").rstrip("/")
    timeout_seconds = _get(resolved, "timeout_seconds")
    headers = {"content-type": "application/json"}

    if provider == "anthropic":
        headers["x-api-key"] = key
        headers["anthropic-version"] = "2023-06-01"
        return _http_loop(
            base + "/v1/messages", headers, _anthropic_body(model_name, system, tools),
            _anthropic_parse, _anthropic_results,
            [{"role": "user", "content": prompt}],
            timeout_seconds, budget, max_turns, wall_seconds,
        )

    if key:
        headers["Authorization"] = "Bearer " + key
    token_key = "max_completion_tokens" if provider == "openai" else "max_tokens"
    return _http_loop(
        base + "/chat/completions", headers, _openai_body(model_name, tools, token_key),
        _openai_parse, _openai_results,
        [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        timeout_seconds, budget, max_turns, wall_seconds,
    )


def _forward_call(socket_path, params):
    request = {"name": params.get("name"), "arguments": params.get("arguments", {})}
    conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    conn.connect(socket_path)
    with conn, conn.makefile("rwb") as stream:
        stream.write((json.dumps(request) + "\n").encode("utf-8"))
        stream.flush()
        reply = json.loads(stream.readline().decode("utf-8"))
    return {
        "content": [{"type": "text", "text": reply["text"]}],
        "isError": reply["is_error"],
    }


def serve_mcp(socket_path, tools_path):
    with open(tools_path, encoding="utf-8") as handle:
        tools = json.load(handle)
    listed = [
        {"name": t["name"], "description": t["description"], "inputSchema": t["input_schema"]}
        for t in tools
    ]
    for raw in sys.stdin.buffer:
        message = json.loads(raw.decode("utf-8"))
        if "id" not in message:
            continue
        method = message.get("method")
        params = message.get("params") or {}
        reply = {"jsonrpc": "2.0", "id": message["id"]}
        if method == "initialize":
            reply["result"] = {
                "protocolVersion": params.get("protocolVersion"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "hotdocs", "version": "1"},
            }
        elif method == "tools/list":
            reply["result"] = {"tools": listed}
        elif method == "tools/call":
            reply["result"] = _forward_call(socket_path, params)
        else:
            reply["error"] = {"code": -32601, "message": "Method not found"}
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__" and sys.argv[1:2] == ["--mcp-serve"]:
    sys.exit(serve_mcp(sys.argv[2], sys.argv[3]))
