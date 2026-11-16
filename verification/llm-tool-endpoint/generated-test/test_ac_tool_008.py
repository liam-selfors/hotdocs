import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading

import llm_tool_endpoint


def _short_tmpdir():
    # Unix socket paths are length-limited (~104 bytes on macOS), so keep it short.
    base = "/tmp" if os.path.isdir("/tmp") else None
    return tempfile.mkdtemp(prefix="mcp", dir=base)


class _SocketServer:
    def __init__(self, path):
        self.path = path
        self.received = []
        self.raw = []
        self._stop = threading.Event()
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(path)
        self.sock.listen(8)
        self.sock.settimeout(0.2)
        self.thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self.thread.start()

    def _handle(self, conn):
        try:
            conn.settimeout(10)
            buf = b""
            while b"\n" not in buf:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk
            line = buf.split(b"\n", 1)[0]
            self.raw.append(line)
            try:
                self.received.append(json.loads(line.decode("utf-8")))
            except Exception:
                self.received.append({"__unparsed__": line.decode("utf-8", "replace")})
            reply = json.dumps({"text": "r", "is_error": False}) + "\n"
            conn.sendall(reply.encode("utf-8"))
            # Wait briefly for the client to close its end.
            try:
                while conn.recv(65536):
                    pass
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _run(self):
        while not self._stop.is_set():
            try:
                conn, _ = self.sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self._handle(conn)

    def stop(self):
        self._stop.set()
        self.thread.join(timeout=5)
        try:
            self.sock.close()
        except Exception:
            pass


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def test_ac_tool_008_serve_mcp_stdio_session():
    workdir = _short_tmpdir()
    server = None
    try:
        tools_path = os.path.join(workdir, "tools.json")
        with open(tools_path, "w", encoding="utf-8") as fh:
            json.dump(
                [{"name": "t", "description": "d", "input_schema": {"type": "object"}}],
                fh,
            )
        socket_path = os.path.join(workdir, "s.sock")
        server = _SocketServer(socket_path)
        server.start()

        module_file = os.path.abspath(llm_tool_endpoint.__file__)

        messages = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "t", "arguments": {"a": 1}},
            },
            {"jsonrpc": "2.0", "id": 4, "method": "bogus/method", "params": {}},
        ]
        stdin_data = "".join(json.dumps(m) + "\n" for m in messages)

        proc = subprocess.run(
            [sys.executable, module_file, "--mcp-serve", socket_path, tools_path],
            input=stdin_data.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=workdir,
            timeout=120,
        )

        stdout = proc.stdout.decode("utf-8")
        stderr = proc.stderr.decode("utf-8", "replace")
        lines = [ln for ln in stdout.splitlines() if ln.strip()]
        assert len(lines) == 4, f"expected 4 reply lines, got {lines!r}; stderr={stderr}"

        replies = [json.loads(ln) for ln in lines]
        by_id = {}
        for r in replies:
            assert "id" in r, f"reply without id: {r!r}"
            by_id[r["id"]] = r
        assert set(by_id) == {1, 2, 3, 4}, f"reply ids: {sorted(by_id, key=str)}"

        r1 = by_id[1]["result"]
        assert r1["protocolVersion"] == "2025-06-18"
        assert r1["capabilities"] == {"tools": {}}

        r2 = by_id[2]["result"]
        assert r2["tools"][0]["inputSchema"] == {"type": "object"}

        r3 = by_id[3]["result"]
        assert r3 == {"content": [{"type": "text", "text": "r"}], "isError": False}
        assert server.received == [{"name": "t", "arguments": {"a": 1}}], server.raw

        assert "error" in by_id[4], by_id[4]
        assert by_id[4]["error"]["code"] == -32601

        assert proc.returncode == 0, f"exit {proc.returncode}; stderr={stderr}"
    finally:
        if server is not None:
            server.stop()
        shutil.rmtree(workdir, ignore_errors=True)