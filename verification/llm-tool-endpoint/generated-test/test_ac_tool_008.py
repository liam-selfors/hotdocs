# hotdocs-criterion: sha256:c44071575d56d1ffac4356e45fb11492d7c39d462a9809e4357c1a4f3309d0c6
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import llm_tool_endpoint


def _short_tmpdir():
    base = "/tmp" if os.path.isdir("/tmp") else None
    return tempfile.mkdtemp(prefix="ac8", dir=base)


class _SocketServer:
    def __init__(self, path):
        self.path = path
        self.received = []
        self.errors = []
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(path)
        self.sock.listen(8)
        self.sock.settimeout(0.5)
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
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
                buf = b""
                while b"\n" not in buf:
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                line = buf.split(b"\n", 1)[0]
                if line.strip():
                    self.received.append(json.loads(line.decode("utf-8")))
                reply = json.dumps({"text": "r", "is_error": False}) + "\n"
                conn.sendall(reply.encode("utf-8"))
            except Exception as exc:  # pragma: no cover - diagnostic
                self.errors.append(repr(exc))
            finally:
                try:
                    conn.close()
                except OSError:
                    pass

    def stop(self):
        self._stop.set()
        try:
            self.sock.close()
        except OSError:
            pass
        self.thread.join(timeout=5)


def test_ac_tool_008_serve_mcp_stdio_session():
    workdir = _short_tmpdir()
    try:
        tools_path = os.path.join(workdir, "tools.json")
        tools = [{"name": "t", "description": "d", "input_schema": {"type": "object"}}]
        Path(tools_path).write_text(json.dumps(tools), encoding="utf-8")

        socket_path = os.path.join(workdir, "s.sock")
        server = _SocketServer(socket_path)
        server.start()
        try:
            module_file = str(Path(llm_tool_endpoint.__file__).resolve())
            requests = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                            "clientInfo": {"name": "test", "version": "0"}}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                 "params": {"name": "t", "arguments": {"a": 1}}},
                {"jsonrpc": "2.0", "id": 4, "method": "bogus/method", "params": {}},
            ]
            stdin_data = "".join(json.dumps(r) + "\n" for r in requests)

            proc = subprocess.run(
                [sys.executable, module_file, "--mcp-serve", socket_path, tools_path],
                input=stdin_data.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
                cwd=workdir,
            )
        finally:
            server.stop()

        stderr_text = proc.stderr.decode("utf-8", "replace")
        assert proc.returncode == 0, stderr_text

        lines = [ln for ln in proc.stdout.decode("utf-8").splitlines() if ln.strip()]
        assert len(lines) == 4, (lines, stderr_text)
        replies = [json.loads(ln) for ln in lines]
        by_id = {r.get("id"): r for r in replies}
        assert set(by_id) == {1, 2, 3, 4}, replies

        r1 = by_id[1]
        assert r1["jsonrpc"] == "2.0"
        assert r1["result"]["protocolVersion"] == "2025-06-18"
        assert r1["result"]["capabilities"] == {"tools": {}}

        r2 = by_id[2]
        assert r2["result"]["tools"][0]["inputSchema"] == {"type": "object"}

        r3 = by_id[3]
        assert r3["result"] == {"content": [{"type": "text", "text": "r"}], "isError": False}
        assert server.errors == [], server.errors
        assert server.received == [{"name": "t", "arguments": {"a": 1}}]

        r4 = by_id[4]
        assert "result" not in r4
        assert r4["error"]["code"] == -32601
    finally:
        shutil.rmtree(workdir, ignore_errors=True)