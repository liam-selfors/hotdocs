# hotdocs-criterion: sha256:05c11c926a3c65037a48123441e2e5624b02f6f37073eda542468691a3bd84eb
import hashlib
import io
import json
import contextlib
from pathlib import Path

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_CACHE_MANAGER_TEMPLATE_HEAD = (
    "import json\n"
    "from dataclasses import dataclass, asdict, is_dataclass\n"
    "\n"
    "LOG_PATH = "
)

FAKE_CACHE_MANAGER_TEMPLATE_BODY = (
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
    "def _log(record):\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(record, sort_keys=True, default=str) + '\\n')\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    _log({'call': 'get', 'gate_version': cache_key.gate_version})\n"
    "    return Miss()\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    payload = result.payload\n"
    "    if is_dataclass(payload):\n"
    "        payload = asdict(payload)\n"
    "    _log({'call': 'put', 'gate_version': cache_key.gate_version,\n"
    "          'gate_type': result.gate_type, 'payload': payload})\n"
    "    return None\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    return '2026-01-01T00:00:00Z'\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {'entry_count': 0}\n"
)


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # Generated component content that matches nothing in the corpus.
    comp_dir = repo_root / "gen" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "foo.py").write_text(
        "def alpha(beta, gamma):\n"
        "    return beta + gamma + delta + epsilon + zeta + eta + theta\n",
        encoding="utf-8",
    )

    # Usable corpus whose hashes cannot match the component's windows.
    unrelated = hashlib.sha256(
        "\x1f".join(["unrelated"] * 9).encode("utf-8")
    ).hexdigest()
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": [unrelated],
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_bytes = json.dumps(corpus).encode("utf-8")
    corpus_path.write_bytes(corpus_bytes)

    # Fake cache-manager, flat-module shape.
    log_path = tmp_path / "cache_calls.log"
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER_TEMPLATE_HEAD + repr(str(log_path)) + FAKE_CACHE_MANAGER_TEMPLATE_BODY,
        encoding="utf-8",
    )

    return repo_root, corpus_path, corpus_bytes, log_path


def _read_log(log_path):
    if not log_path.is_file():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _assert_clean_record(result, expected_gate_version):
    assert result is not None
    assert field(result, "component_id") == "comp-foo"
    assert field(result, "evaluated") is True
    assert field(result, "reason") is None
    assert field(result, "gate_version") == expected_gate_version
    score = field(result, "similarity_score")
    assert score is not None
    assert float(score) == 0.0
    assert float(field(result, "block_threshold")) == 0.70
    assert field(result, "blocked") is False
    assert list(field(result, "matches")) == []
    assert field(result, "notified") is False
    assert field(result, "notification_delivery_error") is None


def test_clean_scan_still_produces_full_record(tmp_path, monkeypatch):
    repo_root, corpus_path, corpus_bytes, log_path = _build_repo(tmp_path)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    expected_gate_version = (
        "license_scanner@4.0.3+" + hashlib.sha256(corpus_bytes).hexdigest()[:12]
    )

    result = license_scanner.scan("comp-foo", repo_root)
    _assert_clean_record(result, expected_gate_version)
    assert field(result, "cache_hit") is False

    # The clean result is recorded (persisted as a payload), not omitted.
    puts = [r for r in _read_log(log_path) if r["call"] == "put"]
    assert len(puts) == 1
    put = puts[0]
    assert put["gate_type"] == "license_scanner"
    payload = put["payload"]
    for key in ("component_id", "gate_version", "similarity_score", "blocked", "matches"):
        assert key in payload
    assert payload["component_id"] == "comp-foo"
    assert payload["evaluated"] is True
    assert payload["blocked"] is False
    assert payload["matches"] == []
    assert float(payload["similarity_score"]) == 0.0


def test_clean_scan_cli_json_emits_record(tmp_path, monkeypatch):
    repo_root, corpus_path, corpus_bytes, log_path = _build_repo(tmp_path)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    expected_gate_version = (
        "license_scanner@4.0.3+" + hashlib.sha256(corpus_bytes).hexdigest()[:12]
    )

    out = io.StringIO()
    err = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = license_scanner.main(
            ["comp-foo", "--repo-root=" + str(repo_root), "--format=json"]
        )
    assert code == 0, err.getvalue()
    document = json.loads(out.getvalue())
    assert isinstance(document, dict)
    _assert_clean_record(document, expected_gate_version)
    assert "cache_hit" in document