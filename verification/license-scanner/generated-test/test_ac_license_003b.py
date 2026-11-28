# hotdocs-criterion: sha256:df19645931537ab62d896876606bde86b34469c92361269f2afe2072392945c6
"""AC-LICENSE-003b: a below-threshold match against a "high" risk_tier
reference, with VAR-COMPLIANCE-WEBHOOK-URL configured, is not blocked but
is notified."""

import hashlib
import http.server
import json
import re
import threading
from pathlib import Path

import pytest

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_ID = "comp-foo"
SLUG = "foo"


def _strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'""".*?"""', " ", text, flags=re.S)
    text = re.sub(r"'''.*?'''", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"#[^\n]*", " ", text)
    return text


def _window_hashes(text):
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", _strip_comments(text))]
    out = []
    for i in range(len(tokens) - 8):
        joined = "\x1f".join(tokens[i:i + 9])
        h = hashlib.sha256(joined.encode("utf-8")).hexdigest()
        if h not in out:
            out.append(h)
    return out


FAKE_CACHE_MANAGER = (
    "from dataclasses import dataclass\n"
    "from typing import Any\n"
    "\n"
    "LOG_PATH = {log!r}\n"
    "\n"
    "\n"
    "class SchemaValidationError(ValueError):\n"
    "    pass\n"
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
    "@dataclass\n"
    "class CacheKey:\n"
    "    spec_bundle_hash: str\n"
    "    gate_inputs_hash: str\n"
    "    gate_version: str\n"
    "    model_pin: str\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class CachedResult:\n"
    "    gate_type: str\n"
    "    payload: Any\n"
    "    stored_at: str\n"
    "\n"
    "\n"
    "def _log(line):\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    _log('get')\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    _log('put')\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    import datetime\n"
    "    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {{'entry_count': 0}}\n"
)


class _Hook(http.server.BaseHTTPRequestHandler):
    calls = []

    def _ok(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        _Hook.calls.append(self.command)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")

    do_POST = _ok
    do_PUT = _ok
    do_GET = _ok

    def log_message(self, *args):
        pass


@pytest.fixture
def webhook_url():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Hook)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:" + str(server.server_address[1]) + "/hook"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def repo(tmp_path, monkeypatch, webhook_url):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Component source: 18 distinct tokens -> 10 distinct 9-token windows.
    source = "\n".join("tok" + chr(ord("a") + i) for i in range(18)) + "\n"
    for d in (repo_root / "gen" / SLUG, repo_root / "legacy" / SLUG):
        d.mkdir(parents=True)
        (d / "foo.py").write_text(source, encoding="utf-8")

    comp_dir = repo_root / "specs" / "components" / SLUG
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n",
        encoding="utf-8",
    )

    windows = _window_hashes(source)
    assert len(windows) == 10
    # 9 of 10 windows match -> score 0.9, below threshold 0.95.
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.95,
        "entries": [
            {
                "reference_id": "ref-high-001",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": windows[:9],
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    log_path = tmp_path / "cache_calls.log"
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER.replace("{log!r}", repr(str(log_path))).replace("{{", "{").replace("}}", "}"),
        encoding="utf-8",
    )

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", webhook_url)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)
    return repo_root


def test_below_threshold_high_risk_tier_is_notified_but_not_blocked(repo):
    result = license_scanner.scan(COMPONENT_ID, repo)

    assert field(result, "evaluated") is True
    score = field(result, "similarity_score")
    threshold = field(result, "block_threshold")
    assert score is not None and threshold is not None
    assert score < threshold
    assert score == pytest.approx(0.9)

    matches = field(result, "matches")
    assert any(field(m, "risk_tier") == "high" for m in matches)

    # The Then clause: not blocked, yet notified.
    assert field(result, "blocked") is False
    assert field(result, "notified") is True


def test_cli_json_reports_not_blocked_but_notified(repo, capsys):
    code = license_scanner.main([COMPONENT_ID, "--repo-root", str(repo), "--format=json"])
    out = capsys.readouterr().out
    doc = json.loads(out)

    assert code == 0
    assert doc["evaluated"] is True
    assert doc["similarity_score"] < doc["block_threshold"]
    assert doc["blocked"] is False
    assert doc["notified"] is True