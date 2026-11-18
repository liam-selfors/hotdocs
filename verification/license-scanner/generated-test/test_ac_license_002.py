# hotdocs-criterion: sha256:65e51ba51f26a6a9668f452963dfce84c7d6f9182fee859aa5f996e549951b08
import dataclasses
import hashlib
import json
import os
import sys
import textwrap
from pathlib import Path

import pytest

import license_scanner


COMPONENT_ID = "comp-widget"
COMPONENT_SLUG = "widget"


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _as_dict(value):
    if isinstance(value, dict):
        return dict(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return dataclasses.asdict(value)
    if hasattr(value, "_asdict"):
        return dict(value._asdict())
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    raise AssertionError("LicenseScanResult is neither dict-like nor object-like: %r" % (value,))


def _write_fake_cache_manager(repo_root: Path, log_path: Path) -> None:
    fake_dir = repo_root / "gen" / "cache-manager"
    fake_dir.mkdir(parents=True, exist_ok=True)
    source = textwrap.dedent(
        """
        import dataclasses
        import json
        from datetime import datetime, timezone

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


        def get(cache_key, *, repo_root=None):
            _log({{"call": "get", "gate_version": getattr(cache_key, "gate_version", None)}})
            return Miss()


        def put(cache_key, result, *, repo_root=None):
            payload = result.get("payload") if isinstance(result, dict) else getattr(result, "payload", None)
            _log({{"call": "put", "payload": payload}})
            return None


        def now_iso():
            return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


        def stats(*, repo_root=None):
            return {{"entry_count": 0}}
        """
    ).format(log_path=str(log_path))
    (fake_dir / "cache_manager.py").write_text(source, encoding="utf-8")


def _write_component_source(repo_root: Path) -> None:
    gen_dir = repo_root / "gen" / COMPONENT_SLUG
    gen_dir.mkdir(parents=True, exist_ok=True)
    source = textwrap.dedent(
        """
        def compute_widget_total(alpha, beta, gamma, delta):
            first_value = alpha + beta
            second_value = gamma * delta
            combined_result = first_value - second_value
            return combined_result + 12345


        class WidgetAccumulator:
            def __init__(self, seed_value):
                self.running_total = seed_value
                self.observations = []

            def record_observation(self, sample):
                self.observations.append(sample)
                self.running_total = self.running_total + sample
                return self.running_total
        """
    )
    (gen_dir / "widget.py").write_text(source, encoding="utf-8")


def _write_nonmatching_corpus(repo_root: Path) -> bytes:
    unrelated = [
        hashlib.sha256(("totally-unrelated-window-%d" % i).encode("utf-8")).hexdigest()
        for i in range(5)
    ]
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": unrelated,
            }
        ],
    }
    data = json.dumps(corpus, indent=2).encode("utf-8")
    (repo_root / "corpus.json").write_bytes(data)
    return data


@pytest.fixture
def clean_repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "cache_calls.log"
    _write_fake_cache_manager(repo_root, log_path)
    _write_component_source(repo_root)
    corpus_bytes = _write_nonmatching_corpus(repo_root)

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", "corpus.json")
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)
    return repo_root, corpus_bytes, log_path


def _assert_clean_record(result, corpus_bytes):
    assert result is not None, "a clean scan must still produce a LicenseScanResult, never nothing"

    assert _field(result, "component_id") == COMPONENT_ID
    assert _field(result, "evaluated") is True
    assert _field(result, "reason") is None

    expected_gate_version = "license_scanner@4.0.3+" + hashlib.sha256(corpus_bytes).hexdigest()[:12]
    assert _field(result, "gate_version") == expected_gate_version

    score = _field(result, "similarity_score")
    threshold = _field(result, "block_threshold")
    assert isinstance(score, (int, float)) and not isinstance(score, bool)
    assert isinstance(threshold, (int, float)) and not isinstance(threshold, bool)
    assert threshold == pytest.approx(0.70)
    assert score == pytest.approx(0.0)
    assert score < threshold

    assert _field(result, "blocked") is False
    matches = _field(result, "matches")
    assert isinstance(matches, list)
    assert matches == []
    assert _field(result, "notified") is False
    assert _field(result, "notification_delivery_error") is None


def test_clean_scan_still_produces_full_recordable_result(clean_repo):
    repo_root, corpus_bytes, _log_path = clean_repo

    result = license_scanner.scan(COMPONENT_ID, repo_root)

    _assert_clean_record(result, corpus_bytes)

    record = _as_dict(result)
    required_keys = {
        "component_id",
        "gate_version",
        "evaluated",
        "reason",
        "similarity_score",
        "block_threshold",
        "blocked",
        "matches",
        "notified",
        "notification_delivery_error",
        "cache_hit",
    }
    missing = required_keys - set(record.keys())
    assert not missing, "clean LicenseScanResult omits fields: %r" % sorted(missing)

    # The record must be serializable as-is into the provenance manifest's
    # `license_scan` field: a clean result is recorded, not omitted.
    manifest = {"license_scan": record}
    round_tripped = json.loads(json.dumps(manifest))
    assert round_tripped["license_scan"] is not None
    assert round_tripped["license_scan"]["blocked"] is False
    assert round_tripped["license_scan"]["evaluated"] is True
    assert round_tripped["license_scan"]["component_id"] == COMPONENT_ID


def test_clean_scan_cli_json_emits_record_and_exits_zero(clean_repo, capsys):
    repo_root, corpus_bytes, _log_path = clean_repo

    try:
        code = license_scanner.main([COMPONENT_ID, "--repo-root=%s" % repo_root, "--format=json"])
    except SystemExit as exc:
        code = exc.code
    if code is None:
        code = 0

    out = capsys.readouterr().out
    assert code == 0, "a clean, not-blocked scan must exit 0; stdout=%r" % out
    assert out.strip(), "a clean scan must still print its LicenseScanResult, not nothing"

    printed = json.loads(out.strip())
    assert isinstance(printed, dict)
    _assert_clean_record(printed, corpus_bytes)