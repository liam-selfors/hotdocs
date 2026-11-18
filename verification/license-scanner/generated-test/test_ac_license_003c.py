# hotdocs-criterion: sha256:bf2849a8c7d5527db331b1b1baec586b2d0b3a95a38fa0acb4b985a8c81a1f7c
import hashlib
import json
import os
import re
import socket
import sys
from pathlib import Path

import pytest

import license_scanner


COMPONENT_ID = "comp-widget"
COMPONENT_SLUG = "widget"


def _field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


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
    for i in range(len(tokens) - 8):
        window = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(window.encode("utf-8")).hexdigest())
    return sorted(hashes)


COMPONENT_SOURCE = (
    "def compute_total(items, factor):\n"
    "    total = 0\n"
    "    for item in items:\n"
    "        total = total + item * factor + 17\n"
    "    if total > 1000:\n"
    "        total = total - 250\n"
    "    return total\n"
    "\n"
    "def scale_values(values, multiplier, offset):\n"
    "    result = []\n"
    "    for value in values:\n"
    "        result.append(value * multiplier + offset)\n"
    "    return result\n"
)


FAKE_CACHE_MANAGER = '''
import json
from dataclasses import dataclass, asdict, is_dataclass
from pathlib import Path
from datetime import datetime, timezone

_LOG_PATH = {log_path!r}


def _log(record):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\\n")


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
    _log({{"op": "get", "gate_version": getattr(cache_key, "gate_version", None)}})
    return Miss()


def put(cache_key, result, *, repo_root=None):
    payload = result.payload if not isinstance(result, dict) else result.get("payload")
    if is_dataclass(payload):
        payload = asdict(payload)
    _log({{"op": "put", "gate_version": getattr(cache_key, "gate_version", None),
           "gate_type": getattr(result, "gate_type", None), "payload": payload}})
    return None


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {{"entry_count": 0}}
'''


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    comp_dir = repo_root / "gen" / COMPONENT_SLUG
    comp_dir.mkdir(parents=True)
    (comp_dir / "widget.py").write_text(COMPONENT_SOURCE, encoding="utf-8")

    log_path = tmp_path / "cache_calls.log"
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER.format(log_path=str(log_path)), encoding="utf-8"
    )

    hashes = _window_hashes(COMPONENT_SOURCE)
    assert len(hashes) > 0
    corpus = {
        "corpus_version": 1,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-low",
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": hashes,
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)

    connect_attempts = []
    real_connect = socket.socket.connect
    real_create_connection = socket.create_connection

    def _record_connect(self, address, *args, **kwargs):
        connect_attempts.append(address)
        raise OSError("network disabled in test")

    def _record_create_connection(address, *args, **kwargs):
        connect_attempts.append(address)
        raise OSError("network disabled in test")

    monkeypatch.setattr(socket.socket, "connect", _record_connect)
    monkeypatch.setattr(socket, "create_connection", _record_create_connection)

    return {
        "repo_root": repo_root,
        "corpus_path": corpus_path,
        "log_path": log_path,
        "connect_attempts": connect_attempts,
    }


def _assert_blocked_low_risk_not_notified(result):
    assert _field(result, "component_id") == COMPONENT_ID
    assert _field(result, "evaluated") is True
    assert _field(result, "reason") is None

    score = _field(result, "similarity_score")
    threshold = _field(result, "block_threshold")
    assert score is not None and threshold is not None
    assert float(threshold) == pytest.approx(0.70)
    assert float(score) >= float(threshold)

    assert _field(result, "blocked") is True
    assert _field(result, "notified") is False
    assert _field(result, "notification_delivery_error") is None

    matches = _field(result, "matches")
    assert matches, "a flagged result must carry its matches"
    tiers = [_field(m, "risk_tier") for m in matches]
    assert "high" not in tiers
    ref_ids = [_field(m, "reference_id") for m in matches]
    assert "ref-low" in ref_ids
    for m in matches:
        if _field(m, "reference_id") == "ref-low":
            assert _field(m, "risk_tier") == "low"
            assert _field(m, "license_family") == "MIT"

    gate_version = _field(result, "gate_version")
    assert isinstance(gate_version, str)
    assert gate_version.startswith("license_scanner@4.0.1+")


def test_blocked_low_risk_without_webhook_is_not_notified_but_recorded(scenario):
    result = license_scanner.scan(COMPONENT_ID, scenario["repo_root"])

    assert result is not None, "the LicenseScanResult must still be produced"
    _assert_blocked_low_risk_not_notified(result)

    assert scenario["connect_attempts"] == [], (
        "no notification may be attempted when VAR_COMPLIANCE_WEBHOOK_URL is absent"
    )

    log_path = scenario["log_path"]
    if log_path.exists():
        records = [
            json.loads(line)
            for line in log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        puts = [r for r in records if r.get("op") == "put"]
        for rec in puts:
            assert rec.get("gate_type") == "license_scanner"
            payload = rec.get("payload") or {}
            if isinstance(payload, dict) and "blocked" in payload:
                assert payload["blocked"] is True
            if isinstance(payload, dict) and "notified" in payload:
                assert payload["notified"] is False


def test_cli_blocked_low_risk_without_webhook(scenario, capsys):
    exit_code = license_scanner.main(
        [COMPONENT_ID, "--repo-root=" + str(scenario["repo_root"]), "--format=json"]
    )
    out = capsys.readouterr().out
    assert exit_code == 1

    start = out.find("{")
    end = out.rfind("}")
    assert start != -1 and end > start, "json output expected"
    result = json.loads(out[start:end + 1])

    _assert_blocked_low_risk_not_notified(result)
    assert scenario["connect_attempts"] == []