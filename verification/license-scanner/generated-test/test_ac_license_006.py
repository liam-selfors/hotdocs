# hotdocs-criterion: sha256:3e464d20f67dc905ff8c2979ed4339845b3fa6a7498035485e1a1dcc815c79e0
import io
import json
import os
import sys
import contextlib
from pathlib import Path

import pytest

import license_scanner


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


FAKE_CACHE_MANAGER_TEMPLATE = '''
import dataclasses
import json
import datetime

_LOG_PATH = {log_path!r}


def _log(record):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, default=str) + "\\n")


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


_REQUIRED = {{
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
}}


def get(cache_key, *, repo_root=None):
    _log({{"op": "get", "gate_version": getattr(cache_key, "gate_version", None)}})
    return Miss()


def put(cache_key, result, *, repo_root=None):
    payload = result.get("payload") if isinstance(result, dict) else getattr(result, "payload", None)
    gate_type = result.get("gate_type") if isinstance(result, dict) else getattr(result, "gate_type", None)
    component_id = None
    if isinstance(payload, dict):
        component_id = payload.get("component_id")
    else:
        component_id = getattr(payload, "component_id", None)
    _log({{"op": "put", "gate_type": gate_type, "component_id": component_id}})
    key_gate_type = str(getattr(cache_key, "gate_version", "")).split("@", 1)[0]
    if gate_type != key_gate_type:
        raise SchemaValidationError("gate_type mismatch")
    if isinstance(payload, dict):
        for k in _REQUIRED.get(gate_type, []):
            if k not in payload:
                raise SchemaValidationError("missing key " + k)
    return None


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {{"entry_count": 0}}
'''


SOURCE_TEXT = '''
def compute_total(items, factor):
    total = 0
    for item in items:
        total = total + item * factor
    return total


def describe_widget(name, size, color, weight):
    return name + str(size) + color + str(weight)
'''


def _make_repo(tmp_path, slugs):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "cache_calls.log"
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(
        FAKE_CACHE_MANAGER_TEMPLATE.format(log_path=str(log_path)), encoding="utf-8"
    )
    for slug in slugs:
        comp_dir = repo_root / "gen" / slug
        comp_dir.mkdir(parents=True)
        module_name = slug.replace("-", "_")
        (comp_dir / (module_name + ".py")).write_text(SOURCE_TEXT, encoding="utf-8")
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": ["0" * 64],
            }
        ],
    }
    corpus_path = repo_root / "corpus.json"
    corpus_path.write_text(json.dumps(corpus), encoding="utf-8")
    return repo_root, log_path, corpus_path


def _read_log(log_path):
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def _assert_single_result(result, component_id):
    assert result is not None
    assert not isinstance(result, (list, tuple, set)), (
        "scan must return exactly one LicenseScanResult, not a collection"
    )
    assert _field(result, "component_id") == component_id
    assert _field(result, "gate_version") is not None
    evaluated = _field(result, "evaluated")
    assert isinstance(evaluated, bool)
    assert isinstance(_field(result, "blocked"), bool)
    matches = _field(result, "matches")
    assert isinstance(matches, list)


@pytest.fixture
def clean_env(monkeypatch):
    for name in (
        "VAR_LICENSE_CORPUS_PATH",
        "VAR_COMPLIANCE_WEBHOOK_URL",
        "VAR_CACHE_STORE_URL",
    ):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_scan_produces_exactly_one_result_with_usable_corpus(tmp_path, clean_env):
    repo_root, log_path, corpus_path = _make_repo(tmp_path, ["widget"])
    clean_env.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    result = license_scanner.scan("comp-widget", repo_root)

    _assert_single_result(result, "comp-widget")
    assert _field(result, "evaluated") is True

    records = _read_log(log_path)
    puts = [r for r in records if r.get("op") == "put"]
    assert len(puts) == 1, "exactly one result should be stored per fresh scan: %r" % records
    assert puts[0].get("component_id") == "comp-widget"
    assert puts[0].get("gate_type") == "license_scanner"


def test_scan_produces_exactly_one_result_without_corpus(tmp_path, clean_env):
    repo_root, log_path, _corpus_path = _make_repo(tmp_path, ["widget"])

    result = license_scanner.scan("comp-widget", repo_root)

    _assert_single_result(result, "comp-widget")
    assert _field(result, "evaluated") is False
    assert _field(result, "reason") == "no-reference-corpus"

    records = _read_log(log_path)
    puts = [r for r in records if r.get("op") == "put"]
    assert len(puts) <= 1
    for p in puts:
        assert p.get("component_id") == "comp-widget"


def test_each_component_gets_its_own_single_result(tmp_path, clean_env):
    repo_root, log_path, corpus_path = _make_repo(tmp_path, ["widget", "gadget"])
    clean_env.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    result_a = license_scanner.scan("comp-widget", repo_root)
    result_b = license_scanner.scan("comp-gadget", repo_root)

    _assert_single_result(result_a, "comp-widget")
    _assert_single_result(result_b, "comp-gadget")

    records = _read_log(log_path)
    puts = [r for r in records if r.get("op") == "put"]
    assert len(puts) == 2, "one stored result per component per scan: %r" % records
    put_ids = sorted(p.get("component_id") for p in puts)
    assert put_ids == ["comp-gadget", "comp-widget"]


def _run_main(argv):
    out = io.StringIO()
    code = None
    with contextlib.redirect_stdout(out):
        try:
            code = license_scanner.main(argv)
        except SystemExit as exc:
            code = exc.code
    if code is None:
        code = 0
    return code, out.getvalue()


def test_cli_json_prints_exactly_one_result_object(tmp_path, clean_env):
    repo_root, _log_path, corpus_path = _make_repo(tmp_path, ["widget"])
    clean_env.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    code, out = _run_main(
        ["comp-widget", "--repo-root=" + str(repo_root), "--format=json"]
    )

    assert code == 0, out
    parsed = json.loads(out.strip())
    assert isinstance(parsed, dict), "CLI must print exactly one LicenseScanResult object"
    assert parsed.get("component_id") == "comp-widget"
    assert "blocked" in parsed
    assert "similarity_score" in parsed
    assert "matches" in parsed