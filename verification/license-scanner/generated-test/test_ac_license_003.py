# hotdocs-criterion: sha256:c0cccb1c642f74103d6e287e9d68a79dd822a76dd43084c3c566f6c23f3f8ed4
import hashlib
import http.server
import json
import re
import threading

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER = (
    "import dataclasses\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class CacheKey:\n"
    "    spec_bundle_hash: str\n"
    "    gate_inputs_hash: str\n"
    "    gate_version: str\n"
    "    model_pin: str\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class CachedResult:\n"
    "    gate_type: str\n"
    "    payload: dict\n"
    "    stored_at: str\n"
    "\n"
    "\n"
    "class Miss:\n"
    "    def __eq__(self, other):\n"
    "        return isinstance(other, Miss)\n"
    "\n"
    "    def __hash__(self):\n"
    "        return 0\n"
    "\n"
    "\n"
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    import datetime\n"
    "    return datetime.datetime.now(datetime.timezone.utc).strftime("
    + repr("%Y-%m-%dT%H:%M:%SZ")
    + ")\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {" + repr("entry_count") + ": 0}\n"
)


SOURCE_LINES = [
    "def compute_total_value(alpha_items, beta_factor, gamma_offset):",
    "    running_total = 0",
    "    for current_item in alpha_items:",
    "        weighted_amount = current_item * beta_factor + gamma_offset",
    "        running_total = running_total + weighted_amount",
    "    adjusted_result = running_total - gamma_offset * 3",
    "    return adjusted_result",
    "",
    "def render_summary_report(entries_list, header_title, footer_note):",
    "    collected_lines = [header_title]",
    "    for entry_value in entries_list:",
    "        collected_lines.append(entry_value)",
    "    collected_lines.append(footer_note)",
    "    return collected_lines",
    "",
]


def window_hashes(text):
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]
    hashes = set()
    for i in range(len(tokens) - 8):
        window = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return sorted(hashes)


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args):
        pass


def test_blocked_match_on_low_risk_entry_is_notified(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True)
    (cache_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")

    source_text = "\n".join(SOURCE_LINES)
    comp_dir = repo_root / "gen" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "foo.py").write_text(source_text, encoding="utf-8")

    hashes = window_hashes(source_text)
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
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    server = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        webhook_url = "http://127.0.0.1:" + str(server.server_address[1]) + "/hook"
        monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
        monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", webhook_url)

        result = license_scanner.scan("comp-foo", repo_root)
    finally:
        server.shutdown()
        server.server_close()

    assert field(result, "evaluated") is True
    assert field(result, "similarity_score") >= field(result, "block_threshold")
    assert field(result, "blocked") is True

    matches = field(result, "matches")
    assert matches
    tiers = [field(m, "risk_tier") for m in matches]
    assert "high" not in tiers
    assert "low" in tiers

    assert field(result, "notified") is True