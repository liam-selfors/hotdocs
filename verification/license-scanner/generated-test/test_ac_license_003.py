# hotdocs-criterion: sha256:e56fd5226123ac65c3ee7846564e653188836ebfc274ef3183ad09b8027f3149
import hashlib
import http.server
import importlib.util
import json
import re
import sys
import threading
from pathlib import Path

import license_scanner


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SOURCE = (
    "def compute_total(alpha, beta, gamma):\n"
    "    result = alpha + beta * gamma\n"
    "    for index in range(10):\n"
    "        result = result + index * alpha - beta\n"
    "    if result > 100:\n"
    "        return result - gamma\n"
    "    return result + 42\n"
    "\n"
    "\n"
    "class Accumulator:\n"
    "    def __init__(self, start):\n"
    "        self.value = start\n"
    "\n"
    "    def add(self, amount):\n"
    "        self.value = self.value + amount\n"
    "        return self.value\n"
)


def window_hashes(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'""".*?"""', " ", text, flags=re.S)
    text = re.sub(r"'''.*?'''", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"#[^\n]*", " ", text)
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]
    out = set()
    for i in range(len(tokens) - 8):
        window = "\x1f".join(tokens[i:i + 9])
        out.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return sorted(out)


FAKE_CACHE_MANAGER = (
    "import dataclasses\n"
    "from datetime import datetime, timezone\n"
    "\n"
    "LOG_PATH = {log!r}\n"
    "\n"
    "def _log(line):\n"
    "    with open(LOG_PATH, 'a') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class CacheKey:\n"
    "    spec_bundle_hash: str\n"
    "    gate_inputs_hash: str\n"
    "    gate_version: str\n"
    "    model_pin: str\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class CachedResult:\n"
    "    gate_type: str\n"
    "    payload: dict\n"
    "    stored_at: str\n"
    "\n"
    "class Miss:\n"
    "    def __eq__(self, other):\n"
    "        return isinstance(other, Miss)\n"
    "    def __hash__(self):\n"
    "        return 0\n"
    "\n"
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    _log('get')\n"
    "    return Miss()\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    _log('put')\n"
    "    return None\n"
    "\n"
    "def now_iso():\n"
    "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {'entry_count': 0}\n"
)


class _Hook(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *args):
        pass


def test_ac_license_003_blocked_low_risk_match_still_notifies(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    log_path = tmp_path / "cache_calls.log"
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER.replace("{log!r}", repr(str(log_path)))
    )

    comp_dir = repo_root / "gen" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "foo.py").write_text(SOURCE)

    hashes = window_hashes(SOURCE)
    assert hashes
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-low-001",
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": hashes,
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus))

    server = http.server.HTTPServer(("127.0.0.1", 0), _Hook)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = "http://127.0.0.1:" + str(server.server_address[1]) + "/hook"
        monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
        monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", url)
        monkeypatch.chdir(repo_root)

        result = license_scanner.scan("comp-foo", repo_root)
    finally:
        server.shutdown()
        server.server_close()

    assert field(result, "evaluated") is True
    assert field(result, "similarity_score") >= field(result, "block_threshold")
    assert field(result, "blocked") is True

    matches = field(result, "matches")
    assert matches, "a flagged result always carries matches"
    tiers = [field(m, "risk_tier") for m in matches]
    assert "high" not in tiers
    assert "low" in tiers

    assert field(result, "notified") is True