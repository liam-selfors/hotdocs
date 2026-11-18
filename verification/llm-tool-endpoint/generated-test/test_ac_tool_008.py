# hotdocs-criterion: sha256:a683f08f6db2027e30a988611a2f75eab0698c7eef93dc8cb97092ab5d2f305f
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import llm_tool_endpoint


def _read_line(conn):
    buf = b""
    while b"\n" not in buf:
        chunk = conn.recv(65536)
        if not chunk:
            break
        buf += chunk
    return buf.split(b"\n", 1)[0]


class _SocketServer:
    def __init__(self, path):
        self.path = path
        self.received = []
        self.errors = []
        self._stop = threading.Event()
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(path)
        self.sock.listen(8)
        self.sock.settimeout(0.2)
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                conn.settimeout(10)
                line = _read_line(conn)
                try:
                    self.received.append(json.loads(line.decode("utf-8")))
                except Exception as exc:  # record but still answer
                    self.errors.append(repr(exc) + " " + repr(line))
                reply = json.dumps({"text": "r", "is_error": False}) + "\n"
                conn.sendall(reply.encode("utf-8"))
            except Exception as exc:
                self.errors.append(repr(exc))
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    def close(self):
        self._stop.set()
        try:
            self.sock.close()
        except OSError:
            pass
        self.thread.join(timeout=5)


def test_ac_tool_008_serve_mcp_stdio_round_trip():
    # Short directory so the Unix socket path fits the platform limit.
    base = tempfile.mkdtemp(prefix="mcp", dir="/tmp" if os.path.isdir("/tmp") else None)
    sock_path = os.path.join(base, "s.sock")
    tools_path = os.path.join(base, "tools.json")
    tools = [{"name": "t", "description": "d", "input_schema": {"type": "object"}}]
    Path(tools_path).write_text(json.dumps(tools), encoding="utf-8")

    server = _SocketServer(sock_path)
    try:
        module_file = str(Path(llm_tool_endpoint.__file__).resolve())
        messages = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "t", "arguments": {"a": 1}}},
            {"jsonrpc": "2.0", "id": 4, "method": "bogus/method", "params": {}},
        ]
        stdin_text = "".join(json.dumps(m) + "\n" for m in messages)

        proc = subprocess.run(
            [sys.executable, module_file, "--mcp-serve", sock_path, tools_path],
            input=stdin_text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=base,
            timeout=60,
        )
    finally:
        server.close()

    stderr = proc.stderr.decode("utf-8", "replace")
    assert proc.returncode == 0, stderr

    lines = [ln for ln in proc.stdout.decode("utf-8").splitlines() if ln.strip()]
    assert len(lines) == 4, (lines, stderr)
    replies = [json.loads(ln) for ln in lines]
    by_id = {r.get("id"): r for r in replies}
    assert set(by_id) == {1, 2, 3, 4}, replies
    for r in replies:
        assert r.get("jsonrpc") == "2.0"

    r1 = by_id[1]
    assert "result" in r1, r1
    assert r1["result"]["protocolVersion"] == "2025-06-18"
    assert r1["result"]["capabilities"] == {"tools": {}}

    r2 = by_id[2]
    assert "result" in r2, r2
    assert r2["result"]["tools"][0]["inputSchema"] == {"type": "object"}

    r3 = by_id[3]
    assert "result" in r3, r3
    assert r3["result"] == {"content": [{"type": "text", "text": "r"}], "isError": False}

    r4 = by_id[4]
    assert "error" in r4, r4
    assert r4["error"]["code"] == -32601

    assert server.errors == [], server.errors
    assert server.received == [{"name": "t", "arguments": {"a": 1}}]