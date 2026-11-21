"""LLM Tool Endpoint: multi-turn tool-use loops over several providers."""

import dataclasses
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
from pathlib import Path

_MODULE_FILE = os.path.abspath(__file__)

_ANTHROPIC_STOPS = {
    "tool_use": None,
    "pause_turn": None,
    "end_turn": "end_turn",
    "stop_sequence": "end_turn",
    "max_tokens": "truncated",
    "refusal": "refusal",
}

_OPENAI_STOPS = {
    "tool_calls": None,
    "stop": "end_turn",
    "length": "truncated",
    "content_filter": "refusal",
}

_MESSAGES = {
    "auth": "authentication failed",
    "rate_limit": "rate limited by backend",
    "timeout": "request timed out",
    "network": "network or backend failure",
}

_CLI_SETTINGS = '{"autoMemoryEnabled":false,"disableAllHooks":true}'


class ToolUseUnsupported(Exception):
    pass


@dataclasses.dataclass
class ToolLoopResult:
    text: str
    transcript: list
    turns: int
    tool_calls: int
    stop: str
    model_call_error: dict = None

    def to_dict(self):
        return dataclasses.asdict(self)


def _get(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _tool_root():
    for parent in Path(_MODULE_FILE).parents:
        if parent.name == "gen":
            return parent.parent
    return Path(_MODULE_FILE).parent


def _load_endpoint(repo_root):
    rel = Path("gen") / "llm-endpoint" / "llm_endpoint.py"
    path = None
    if repo_root is not None and (Path(repo_root) / rel).exists():
        path = Path(repo_root) / rel
    else:
        path = _tool_root() / rel
    spec = importlib.util.spec_from_file_location("llm_endpoint", str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules["llm_endpoint"] = module
    spec.loader.exec_module(module)
    return module


def _error(category):
    return {"category": category, "message": _MESSAGES[category]}


def _dispatch(name, args, names, execute, counter, max_tool_calls):
    """Return (text, is_error) or None when the call is past the cap."""
    if name not in names:
        return "unknown tool: %s" % name, True
    if not isinstance(args, dict):
        return "arguments must be a JSON object", True
    if counter[0] >= max_tool_calls:
        return None
    counter[0] += 1
    try:
        text, is_error = execute(name, args)
    except Exception as exc:  # noqa: BLE001 - any tool failure goes back to the model
        return "tool error: %s: %s" % (type(exc).__name__, exc), True
    return text, bool(is_error)


def _post(url, headers, body, timeout):
    request = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST"
    )
    with urllib.request.urlopen(request, timeout=timeout) as reply:
        raw = reply.read()
    return json.loads(raw)


def _send(url, headers, body, timeout):
    """Return (data, category); exactly one is None."""
    try:
        return _post(url, headers, body, timeout), None
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            return None, "auth"
        if exc.code == 429:
            return None, "rate_limit"
        if exc.code in (408, 504):
            return None, "timeout"
        return None, "network"
    except TimeoutError:
        return None, "timeout"
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError):
            return None, "timeout"
        return None, "network"
    except (OSError, http.client.HTTPException, ValueError):
        return None, "network"


def _anthropic_text(data):
    if data is None:
        return ""
    return "".join(
        b.get("text") or "" for b in data["content"] if b.get("type") == "text"
    )


def _openai_text(data):
    if data is None:
        return ""
    return data["choices"][0]["message"].get("content") or ""


def _http_loop(system, prompt, provider, resolved, key, tools, execute,
               max_turns, max_tool_calls, wall_seconds, start):
    anthropic = provider == "anthropic"
    base = _get(resolved, "base_url").rstrip("/")
    model = _get(resolved, "model")
    timeout_seconds = float(_get(resolved, "timeout_seconds"))
    names = {t["name"] for t in tools}

    if anthropic:
        url = base + "/v1/messages"
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        base_body = {
            "model": model,
            "max_tokens": 32000,
            "system": [{"type": "text", "text": system,
                        "cache_control": {"type": "ephemeral"}}],
            "tools": [{"name": t["name"], "description": t["description"],
                       "input_schema": t["input_schema"]} for t in tools],
            "tool_choice": {"type": "auto"},
        }
        messages = [{"role": "user", "content": prompt}]
        text_of = _anthropic_text
    else:
        url = base + "/chat/completions"
        headers = {"content-type": "application/json"}
        if key:
            headers["Authorization"] = "Bearer " + key
        base_body = {
            "model": model,
            "tools": [{"type": "function",
                       "function": {"name": t["name"],
                                    "description": t["description"],
                                    "parameters": t["input_schema"]}}
                      for t in tools],
            "tool_choice": "auto",
        }
        if provider == "openai":
            base_body["max_completion_tokens"] = 32000
        else:
            base_body["max_tokens"] = 32000
        messages = [{"role": "system", "content": system},
                    {"role": "user", "content": prompt}]
        text_of = _openai_text

    transcript = list(messages)
    last = None
    turns = 0
    counter = [0]

    def finish(stop, error=None):
        return ToolLoopResult(text_of(last), transcript, turns, counter[0],
                              stop, error)

    while True:
        if turns >= max_turns:
            return finish("budget_exhausted")
        remaining = wall_seconds - (time.monotonic() - start)
        if remaining <= 0:
            return finish("budget_exhausted")
        body = dict(base_body)
        body["messages"] = messages
        transcript = list(messages)
        turns += 1
        data, category = _send(url, headers, body, min(timeout_seconds, remaining))
        if category is not None:
            return finish("error", _error(category))
        try:
            if anthropic:
                content = data["content"]
                reason = data["stop_reason"]
                outcome = _ANTHROPIC_STOPS[reason]
                assistant = {"role": "assistant", "content": content}
                calls = []
                if reason == "tool_use":
                    calls = [(b["id"], b["name"], b["input"])
                             for b in content if b["type"] == "tool_use"]
                _anthropic_text(data)
            else:
                choice = data["choices"][0]
                assistant = choice["message"]
                reason = choice["finish_reason"]
                outcome = _OPENAI_STOPS[reason]
                calls = []
                if reason == "tool_calls":
                    calls = [(c["id"], c["function"]["name"],
                              c["function"]["arguments"])
                             for c in assistant["tool_calls"]]
                _openai_text(data)
        except (KeyError, TypeError, IndexError, AttributeError):
            return finish("error", _error("network"))
        last = data
        transcript.append(assistant)

        if outcome is not None:
            return finish(outcome)
        if anthropic and reason == "pause_turn":
            messages.append(assistant)
            continue

        results = []
        for call_id, name, raw_args in calls:
            if anthropic:
                args = raw_args
            else:
                try:
                    args = json.loads(raw_args)
                except (ValueError, TypeError):
                    args = None
            result = _dispatch(name, args, names, execute, counter, max_tool_calls)
            if result is None:
                return finish("budget_exhausted")
            results.append((call_id, result[0], result[1]))

        messages.append(assistant)
        if anthropic:
            blocks = []
            for call_id, text, is_error in results:
                block = {"type": "tool_result", "tool_use_id": call_id,
                         "content": text}
                if is_error:
                    block["is_error"] = True
                blocks.append(block)
            messages.append({"role": "user", "content": blocks})
        else:
            for call_id, text, _ in results:
                messages.append({"role": "tool", "tool_call_id": call_id,
                                 "content": text})


def _serve_socket(listener, stop_event, handle):
    while not stop_event.is_set():
        try:
            conn, _ = listener.accept()
        except TimeoutError:
            continue
        except OSError:
            return
        with conn:
            conn.settimeout(None)
            reader = conn.makefile("rb")
            for line in reader:
                text, is_error = handle(json.loads(line))
                conn.sendall((json.dumps({"text": text, "is_error": is_error})
                              + "\n").encode("utf-8"))


def _cli_loop(system, prompt, resolved, tools, execute, max_turns,
              max_tool_calls, wall_seconds, claude_command):
    names = {t["name"] for t in tools}
    counter = [0]
    over_cap = [False]

    def handle(request):
        result = _dispatch(request.get("name"), request.get("arguments"),
                           names, execute, counter, max_tool_calls)
        if result is None:
            over_cap[0] = True
            return "tool-call budget exhausted", True
        return result

    tmp = tempfile.mkdtemp()
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stop_event = threading.Event()
    try:
        tools_path = os.path.join(tmp, "tools.json")
        sock_path = os.path.join(tmp, "mcp.sock")
        cfg_path = os.path.join(tmp, "mcp.json")
        with open(tools_path, "w", encoding="utf-8") as fh:
            json.dump(tools, fh)
        listener.bind(sock_path)
        listener.listen()
        listener.settimeout(0.1)
        with open(cfg_path, "w", encoding="utf-8") as fh:
            json.dump({"mcpServers": {"hotdocs": {
                "command": sys.executable,
                "args": [_MODULE_FILE, "--mcp-serve", sock_path, tools_path],
            }}}, fh)
        thread = threading.Thread(target=_serve_socket,
                                  args=(listener, stop_event, handle),
                                  daemon=True)
        thread.start()

        cmd = [claude_command, "-p", "--model", _get(resolved, "model"),
               "--output-format", "stream-json", "--verbose",
               "--tools", "", "--mcp-config", cfg_path, "--strict-mcp-config",
               "--allowedTools"]
        cmd += ["mcp__hotdocs__" + t["name"] for t in tools]
        cmd += ["--no-session-persistence", "--setting-sources", "",
                "--disable-slash-commands", "--settings", _CLI_SETTINGS,
                "--system-prompt", system, "--max-turns", str(max_turns)]

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, cwd=tmp,
                                start_new_session=True)
        killed = False
        try:
            out, _ = proc.communicate(prompt.encode("utf-8"),
                                      timeout=wall_seconds)
        except subprocess.TimeoutExpired:
            killed = True
            os.killpg(proc.pid, signal.SIGKILL)
            out, _ = proc.communicate()
    finally:
        stop_event.set()
        listener.close()
        shutil.rmtree(tmp, ignore_errors=True)

    events = []
    for line in out.decode("utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        events.append(event)
    result = None
    for event in events:
        if isinstance(event, dict) and event.get("type") == "result":
            result = event

    error = None
    if killed or (result is not None
                  and result.get("subtype") == "error_max_turns"):
        stop = "budget_exhausted"
    elif proc.returncode != 0 or result is None:
        if over_cap[0]:
            stop = "budget_exhausted"
        else:
            stop = "error"
            error = _error("network")
    elif over_cap[0]:
        stop = "budget_exhausted"
    else:
        stop = "end_turn"

    text = ""
    turns = 0
    if result is not None:
        text = result.get("result") or ""
        turns = result.get("num_turns") or 0
    return ToolLoopResult(text, events, turns, counter[0], stop, error)


def run_tool_loop(system, prompt, model, tools, execute, *, max_turns=40,
                  max_tool_calls=120, wall_seconds=1800.0, repo_root=None,
                  claude_command="claude"):
    start = time.monotonic()
    endpoint = _load_endpoint(repo_root)
    resolved = endpoint.resolve_provider(model, endpoint.load_config())
    provider = _get(resolved, "provider")
    if provider in ("gemini", "ollama"):
        raise ToolUseUnsupported("tool use is not supported by provider %s"
                                 % provider)
    if provider == "claude-cli":
        return _cli_loop(system, prompt, resolved, tools, execute, max_turns,
                         max_tool_calls, wall_seconds, claude_command)
    key_env = _get(resolved, "api_key_env")
    key = os.environ.get(key_env) if key_env else None
    if provider in ("anthropic", "openai") and not key:
        return ToolLoopResult("", [], 0, 0, "error", _error("auth"))
    return _http_loop(system, prompt, provider, resolved, key, tools, execute,
                      max_turns, max_tool_calls, wall_seconds, start)


def serve_mcp(socket_path, tools_path):
    with open(tools_path, encoding="utf-8") as fh:
        tools = json.load(fh)
    for raw in sys.stdin.buffer:
        msg = json.loads(raw)
        if "id" not in msg:
            continue
        method = msg.get("method")
        params = msg.get("params") or {}
        reply = {"jsonrpc": "2.0", "id": msg["id"]}
        if method == "initialize":
            reply["result"] = {
                "protocolVersion": params.get("protocolVersion"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "hotdocs", "version": "1"},
            }
        elif method == "tools/list":
            reply["result"] = {"tools": [
                {"name": t["name"], "description": t["description"],
                 "inputSchema": t["input_schema"]} for t in tools]}
        elif method == "tools/call":
            request = {"name": params.get("name"),
                       "arguments": params.get("arguments", {})}
            conn = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            conn.connect(socket_path)
            conn.sendall((json.dumps(request) + "\n").encode("utf-8"))
            answer = json.loads(conn.makefile("rb").readline())
            conn.close()
            reply["result"] = {
                "content": [{"type": "text", "text": answer["text"]}],
                "isError": answer["is_error"],
            }
        else:
            reply["error"] = {"code": -32601, "message": "Method not found"}
        sys.stdout.write(json.dumps(reply) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(serve_mcp(sys.argv[2], sys.argv[3]))
