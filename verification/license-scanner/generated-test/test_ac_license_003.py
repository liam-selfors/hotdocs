import hashlib
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

import license_scanner


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _strip_comments(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'""".*?"""', " ", text, flags=re.S)
    text = re.sub(r"'''.*?'''", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"#[^\n]*", " ", text)
    return text


def _window_hashes(text):
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", _strip_comments(text))]
    hashes = set()
    for i in range(len(tokens) - 9 + 1):
        window = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return sorted(hashes)


SOURCE = """def alpha_one(beta, gamma):
    delta = beta + gamma * 42
    epsilon = delta - 7
    return epsilon


def zeta_two(eta, theta, iota):
    kappa = eta * theta + iota
    lam = kappa // 3
    mu = lam + eta - theta
    return mu


def nu_three(xi, omicron):
    pi_value = xi + omicron + 100
    rho = pi_value * 2
    sigma = rho - xi
    return sigma


class TauFour:
    def upsilon(self, phi, chi):
        psi = phi * chi + 5
        omega = psi - phi + chi
        return omega
"""


FAKE_CACHE_MANAGER = '''
from dataclasses import dataclass
from datetime import datetime, timezone

_LOG_PATH = {log_path!r}


def _log(entry):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(entry + "\\n")


@dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return 0


class SchemaValidationError(ValueError):
    pass


def get(cache_key, *, repo_root=None):
    _log("get")
    return Miss()


def put(cache_key, result, *, repo_root=None):
    _log("put")
    return None


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {{"entry_count": 0}}
'''


class _WebhookHandler(BaseHTTPRequestHandler):
    def _ok(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        body = b"{}"
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        self._ok()

    def do_PUT(self):
        self._ok()

    def do_GET(self):
        self._ok()

    def log_message(self, *args, **kwargs):
        pass


@pytest.fixture
def webhook_url():
    server = HTTPServer(("127.0.0.1", 0), _WebhookHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield "http://127.0.0.1:%d/hook" % server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


def test_ac_license_003_blocked_low_risk_match_is_notified(tmp_path, monkeypatch, webhook_url):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Fake cache-manager so no real cache hit can short-circuit the scan.
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    log_path = tmp_path / "cache_manager_calls.log"
    (cm_dir / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER.format(log_path=str(log_path)), encoding="utf-8"
    )

    # Component whose source fully matches a low-risk corpus entry.
    component_id = "comp-sample-widget"
    comp_dir = repo_root / "gen" / "sample-widget"
    comp_dir.mkdir(parents=True)
    (comp_dir / "sample_widget.py").write_text(SOURCE, encoding="utf-8")

    hashes = _window_hashes(SOURCE)
    assert hashes, "fixture source must produce at least one 9-token window"

    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-low-001",
                "license_family": "mit",
                "risk_tier": "low",
                "hashes": hashes,
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", webhook_url)
    monkeypatch.chdir(repo_root)

    result = license_scanner.scan(component_id, Path(repo_root))

    # Preconditions: evaluated against the corpus, blocked, and only low-risk matches.
    assert _field(result, "evaluated") is True
    score = _field(result, "similarity_score")
    threshold = _field(result, "block_threshold")
    assert score is not None and threshold is not None
    assert score >= threshold
    assert _field(result, "blocked") is True

    matches = _field(result, "matches") or []
    assert len(matches) >= 1
    for m in matches:
        assert _field(m, "risk_tier") == "low"
        assert _field(m, "risk_tier") != "high"

    # The criterion: notified because the merge was blocked, independent of low risk_tier.
    assert _field(result, "notified") is True
    # Delivery outcome never affects blocked.
    assert _field(result, "blocked") is True