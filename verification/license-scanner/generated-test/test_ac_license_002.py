import json

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def test_clean_scan_result_is_fully_recorded_not_omitted(tmp_path, monkeypatch):
    component_id = "comp-widget-maker"

    widget_dir = tmp_path / "gen" / "widget-maker"
    widget_dir.mkdir(parents=True)
    (widget_dir / "widget_maker.py").write_text(
        "def compute_widget_price(base_cost, markup_percentage, tax_rate, discount_amount):\n"
        "    adjusted_cost = base_cost + (base_cost * markup_percentage)\n"
        "    taxed_cost = adjusted_cost + (adjusted_cost * tax_rate)\n"
        "    final_price = taxed_cost - discount_amount\n"
        "    return final_price\n"
        "\n"
        "\n"
        "def format_widget_label(widget_name, widget_color, widget_size):\n"
        "    return widget_name + \"_\" + widget_color + \"_\" + widget_size\n"
    )

    corpus_path = tmp_path / "license_corpus.json"
    corpus_path.write_text(
        json.dumps(
            {
                "corpus_version": 1,
                "block_threshold": 0.7,
                "entries": [
                    {
                        "reference_id": "ref-001",
                        "license_family": "GPL",
                        "risk_tier": "high",
                        # deliberately impossible to match any real SHA-256 digest
                        "hashes": ["0" * 64],
                    }
                ],
            }
        )
    )

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)

    log_path = tmp_path / "cache_calls.log"

    fake_cache_src = f'''import dataclasses
import json

LOG_PATH = {str(log_path)!r}


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: object
    stored_at: str


def _pget(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def get(cache_key, *, repo_root=None):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps({{"call": "get"}}) + "\\n")
    return {{"payload": None}}


def put(cache_key, result, *, repo_root=None):
    gate_type = _pget(result, "gate_type")
    payload = _pget(result, "payload")
    if isinstance(payload, dict):
        has_matches_key = "matches" in payload
        has_blocked_key = "blocked" in payload
    else:
        has_matches_key = hasattr(payload, "matches")
        has_blocked_key = hasattr(payload, "blocked")
    record = {{
        "call": "put",
        "gate_type": gate_type,
        "component_id": _pget(payload, "component_id"),
        "gate_version": _pget(payload, "gate_version"),
        "evaluated": _pget(payload, "evaluated"),
        "similarity_score": _pget(payload, "similarity_score"),
        "block_threshold": _pget(payload, "block_threshold"),
        "blocked": _pget(payload, "blocked"),
        "matches": _pget(payload, "matches"),
        "has_matches_key": has_matches_key,
        "has_blocked_key": has_blocked_key,
    }}
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record) + "\\n")
'''

    cache_dir = tmp_path / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True)
    (cache_dir / "cache_manager.py").write_text(fake_cache_src)

    result = license_scanner.scan(component_id, tmp_path)

    assert result is not None

    assert _get(result, "component_id") == component_id
    assert _get(result, "evaluated") is True
    assert _get(result, "reason") is None

    score = _get(result, "similarity_score")
    assert isinstance(score, (int, float))
    assert score == 0.0

    assert _get(result, "block_threshold") == 0.7
    assert _get(result, "blocked") is False
    assert _get(result, "matches") == []
    assert _get(result, "notified") is False
    assert _get(result, "notification_delivery_error") is None
    assert _get(result, "cache_hit") is False

    gate_version = _get(result, "gate_version")
    assert gate_version.startswith("license_scanner@4.0.1+")

    assert log_path.exists(), "cache-manager fake was never invoked; no record was made"
    records = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    put_calls = [rec for rec in records if rec.get("call") == "put"]
    assert len(put_calls) == 1, "expected exactly one put() call recording the clean scan result"

    record = put_calls[0]
    assert record["gate_type"] == "license_scanner"
    assert record["component_id"] == component_id
    assert record["gate_version"] == gate_version
    assert record["evaluated"] is True
    assert record["similarity_score"] == 0.0
    assert record["block_threshold"] == 0.7

    # The whole point of R-LICENSE-002: a clean result's "blocked" and
    # "matches" keys must be explicitly present in the cached/recorded
    # payload, not dropped because there was nothing to flag.
    assert record["has_blocked_key"] is True
    assert record["blocked"] is False
    assert record["has_matches_key"] is True
    assert record["matches"] == []