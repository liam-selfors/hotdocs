# hotdocs-criterion: sha256:09e59863cf225f6631caa058aaddb3ff1817385282e5b57e327dc905b71c2d34
"""AC-LICENSE-009 (covers R-LICENSE-003).

Given a match whose risk_tier is high and VAR-COMPLIANCE-WEBHOOK-URL is
configured, but the webhook call itself raises a network error,
when the scan completes,
then notified is true, notification_delivery_error is populated with
category "network", and blocked is unaffected by this failure.
"""

import hashlib
import json
import re
import socket
from pathlib import Path

import pytest

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER_SOURCE = (
    "from dataclasses import dataclass\n"
    "from typing import Any\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class CacheKey:\n"
    "    spec_bundle_hash: Any\n"
    "    gate_inputs_hash: Any\n"
    "    gate_version: Any\n"
    "    model_pin: Any\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class CachedResult:\n"
    "    gate_type: Any\n"
    "    payload: Any\n"
    "    stored_at: Any\n"
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
)


def _tokens(text):
    return [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]


def _window_hashes(text):
    toks = _tokens(text)
    out = []
    for i in range(len(toks) - 8):
        joined = "\x1f".join(toks[i:i + 9])
        out.append(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return out


def _closed_local_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _build_source():
    lines = []
    for i in range(50):
        lines.append("alpha_" + str(i) + " = beta_" + str(i) + "\n")
    return "".join(lines)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Fake cache-manager (flat-module shape) that always misses.
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER_SOURCE, encoding="utf-8")

    # Minimal fixture component.
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n",
        encoding="utf-8",
    )

    source = _build_source()
    for d in (repo_root / "gen" / "foo", repo_root / "legacy" / "foo"):
        d.mkdir(parents=True, exist_ok=True)
        (d / "foo.py").write_text(source, encoding="utf-8")

    distinct = sorted(set(_window_hashes(source)))
    assert len(distinct) > 20
    # Include ~90% of the component's windows: well above any reporting
    # floor, but below a block_threshold of 1.0, so blocked is false and
    # notification is due solely because of the high risk_tier.
    included = distinct[: (len(distinct) * 9) // 10]
    assert len(included) < len(distinct)

    corpus = {
        "corpus_version": 3,
        "block_threshold": 1.0,
        "entries": [
            {
                "reference_id": "ref-high-001",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": included,
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
                 "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    return repo_root


def test_ac_license_009_webhook_network_error_recorded_not_raised(repo, monkeypatch):
    # Baseline: same scan with no webhook configured.
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    baseline = license_scanner.scan("comp-foo", repo)
    assert field(baseline, "evaluated") is True
    baseline_blocked = field(baseline, "blocked")

    # Webhook configured, but pointing at a closed local port: the call
    # fails with a network error (connection refused).
    port = _closed_local_port()
    monkeypatch.setenv("VAR_COMPLIANCE_WEBHOOK_URL", "http://127.0.0.1:" + str(port) + "/hook")

    result = license_scanner.scan("comp-foo", repo)  # must not raise

    assert field(result, "evaluated") is True
    matches = field(result, "matches")
    assert any(field(m, "risk_tier") == "high" for m in matches), matches

    similarity = field(result, "similarity_score")
    threshold = field(result, "block_threshold")
    assert similarity < threshold

    # notified reflects that a notification was due, not that it was delivered.
    assert field(result, "notified") is True

    err = field(result, "notification_delivery_error")
    assert err is not None
    assert field(err, "category") == "network"
    assert isinstance(field(err, "message"), str)

    # blocked is unaffected by the delivery failure.
    blocked = field(result, "blocked")
    assert blocked is (similarity >= threshold)
    assert blocked is False
    assert blocked == baseline_blocked