"""AC-LICENSE-003b (covers R-LICENSE-003).

Given a similarity score below the block threshold against a reference
entry with risk_tier "high", and VAR-COMPLIANCE-WEBHOOK-URL configured,
when license-scan runs, then blocked is false but notified is true.
"""

import hashlib
import http.server
import json
import threading
from pathlib import Path

import pytest

import license_scanner


COMPONENT_ID = "comp-foo"
COMPONENT_SLUG = "foo"


def _field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _window_hashes(tokens, size=9):
    out = []
    for i in range(len(tokens) - size + 1):
        joined = "\x1f".join(tokens[i:i + size])
        out.append(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return out


FAKE_CACHE_MANAGER = '''
import dataclasses
import datetime
import json
import os


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return hash("Miss")


class SchemaValidationError(ValueError):
    pass


_LOG = {log_path!r}


def _record(entry):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\\n")


def get(cache_key, *, repo_root=None):
    _record({{"call": "get"}})
    return Miss()


def put(cache_key, result, *, repo_root=None):
    _record({{"call": "put"}})
    return None


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {{"entry_count": 0}}
'''


def _make_handler(log_path):
    class Handler(http.server.BaseHTTPRequestHandler):
        def _handle(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                self.rfile.read(length)
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"method": self.command, "path": self.path}) + "\n")
            body = b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            self._handle()

        def do_PUT(self):
            self._handle()

        def do_GET(self):
            self._handle()

        def log_message(self, *args, **kwargs):
            return

    return Handler


@pytest.fixture
def webhook_server(tmp_path):
    log_path = tmp_path / "webhook_calls.log"
    log_path.write_text("", encoding="utf-8")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(str(log_path)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:%d/hook" % server.server_address[1], log_path
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Component source: 30 distinct identifier tokens -> 22 distinct 9-token windows.
    tokens = ["v_%03d" % i for i in range(30)]
    comp_dir = repo_root / "gen" / COMPONENT_SLUG
    comp_dir.mkdir(parents=True)
    (comp_dir / "foo.py").write_text("\n".join(tokens) + "\n", encoding="utf-8")

    windows = _window_hashes(tokens)
    assert len(set(windows)) == 22

    # Entry contains 16 of 22 windows -> score ~0.727, below a 0.95 threshold.
    unrelated = _window_hashes(["zz_%03d" % i for i in range(20)])
    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.95,
        "entries": [
            {
                "reference_id": "ref-high-001",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": windows[:16] + unrelated,
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    cache_log = tmp_path / "cache_calls.log"
    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True)
    (cache_dir / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER.format(log_path=str(cache_log)), encoding="utf-8"
    )

    return repo_root, corpus_path


def test_below_threshold_high_risk_match_notifies_without_blocking(
    tmp_path, monkeypatch, webhook_server
):
    webhook_url, webhook_log = webhook_server
    repo_root, corpus_path = _build_repo(tmp_path)

    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", webhook_url)

    result = license_scanner.scan(COMPONENT_ID, repo_root)

    assert _field(result, "evaluated") is True
    assert _field(result, "reason") is None

    score = _field(result, "similarity_score")
    threshold = _field(result, "block_threshold")
    assert score is not None and threshold is not None
    assert float(threshold) == pytest.approx(0.95)
    assert 0 < float(score) < float(threshold)
    assert float(score) == pytest.approx(16 / 22, abs=1e-6)

    matches = _field(result, "matches") or []
    assert len(matches) >= 1
    assert any(_field(m, "risk_tier") == "high" for m in matches)
    assert any(_field(m, "reference_id") == "ref-high-001" for m in matches)

    # The core of the criterion: not blocked, yet notified.
    assert _field(result, "blocked") is False
    assert _field(result, "notified") is True

    # Webhook attempted at most once (no retry-with-backoff).
    calls = [ln for ln in webhook_log.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(calls) <= 1


def test_cli_exit_code_reflects_not_blocked_while_notified(
    tmp_path, monkeypatch, webhook_server, capsys
):
    webhook_url, _ = webhook_server
    repo_root, corpus_path = _build_repo(tmp_path)

    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", webhook_url)

    code = license_scanner.main(
        [COMPONENT_ID, "--repo-root=%s" % repo_root, "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0

    payload = json.loads(out)
    assert payload.get("blocked") is False
    assert payload.get("notified") is True