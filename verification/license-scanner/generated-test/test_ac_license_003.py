import hashlib
import json
import os
import tempfile
from pathlib import Path

import license_scanner


def _window_hash(tokens):
    joined = "\x1f".join(tokens)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _field(obj, name):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _write_fake_cache_manager(repo_root):
    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True, exist_ok=True)
    (cache_manager_dir / "cache_manager.py").write_text(
        "from dataclasses import dataclass\n"
        "from typing import Any\n"
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
        "class Miss:\n"
        "    pass\n"
        "\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    return Miss()\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    pass\n"
    )


def test_ac_license_003_notified_true_on_block_with_low_risk_tier():
    tokens = [
        "alpha", "beta", "gamma", "delta", "epsilon",
        "zeta", "eta", "theta", "iota",
    ]
    window_hash = _window_hash(tokens)

    with tempfile.TemporaryDirectory() as tmp:
        repo_root = Path(tmp)
        _write_fake_cache_manager(repo_root)

        target_dir = repo_root / "gen" / "target"
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "main.py").write_text(" ".join(tokens) + "\n")

        corpus = {
            "corpus_version": 1,
            "block_threshold": 0.5,
            "entries": [
                {
                    "reference_id": "ref-low-1",
                    "license_family": "mit",
                    "risk_tier": "low",
                    "hashes": [window_hash],
                }
            ],
        }
        corpus_path = repo_root / "license-corpus.json"
        corpus_path.write_text(json.dumps(corpus))

        old_environ = dict(os.environ)
        try:
            os.environ["VAR_LICENSE_CORPUS_PATH"] = str(corpus_path)
            os.environ["VAR_COMPLIANCE_WEBHOOK_URL"] = "https://example.invalid/webhook"

            result = license_scanner.scan("comp-target", repo_root)
        finally:
            os.environ.clear()
            os.environ.update(old_environ)

        assert _field(result, "evaluated") is True
        assert _field(result, "blocked") is True

        matches = _field(result, "matches") or []
        assert len(matches) >= 1
        risk_tiers = {_field(m, "risk_tier") for m in matches}
        assert risk_tiers == {"low"}
        assert "high" not in risk_tiers

        assert _field(result, "notified") is True