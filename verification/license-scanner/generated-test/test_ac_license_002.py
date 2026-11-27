# hotdocs-criterion: sha256:255c68acb48b07f6e4a4619a6d225508e0218b74faf9f49db1c3f8cde42e01b2
import hashlib
import json
from pathlib import Path

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_ID = "comp-foo"
SLUG = "foo"

SOURCE_TEXT = (
    "def compute_totals(orders, tax_rate):\n"
    "    subtotal = 0\n"
    "    for order in orders:\n"
    "        subtotal = subtotal + order.amount * order.quantity\n"
    "    total = subtotal + subtotal * tax_rate\n"
    "    return round(total, 2)\n"
    "\n"
    "\n"
    "class InventoryLedger:\n"
    "    def __init__(self, warehouse_name):\n"
    "        self.warehouse_name = warehouse_name\n"
    "        self.items = {}\n"
    "\n"
    "    def add_item(self, sku, count):\n"
    "        self.items[sku] = self.items.get(sku, 0) + count\n"
    "        return self.items[sku]\n"
)


def _window_hash(tokens):
    return hashlib.sha256("\x1f".join(tokens).encode("utf-8")).hexdigest()


def _write_fake_cache_manager(repo_root):
    base = repo_root / "gen" / "cache-manager"
    base.mkdir(parents=True, exist_ok=True)
    src = (
        "import dataclasses\n"
        "from datetime import datetime, timezone\n"
        "\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str\n"
        "    gate_inputs_hash: str\n"
        "    gate_version: str\n"
        "    model_pin: str\n"
        "\n"
        "\n"
        "@dataclasses.dataclass\n"
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
        "def get(cache_key, *, repo_root=None):\n"
        "    return Miss()\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    return None\n"
        "\n"
        "\n"
        "def now_iso():\n"
        "    return datetime.now(timezone.utc).strftime("
        + repr("%Y-%m-%dT%H:%M:%SZ")
        + ")\n"
        "\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return {" + repr("entry_count") + ": 0}\n"
    )
    (base / "cache_manager.py").write_text(src, encoding="utf-8")


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    gen_dir = repo_root / "gen" / SLUG
    gen_dir.mkdir(parents=True)
    (gen_dir / "foo.py").write_text(SOURCE_TEXT, encoding="utf-8")

    _write_fake_cache_manager(repo_root)

    unrelated_tokens = [
        "zzqx", "unrelated", "corpus", "window", "never",
        "appears", "in", "source", "text",
    ]
    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "MIT",
                "risk_tier": "low",
                "hashes": [
                    _window_hash(unrelated_tokens),
                    hashlib.sha256(b"no-such-window").hexdigest(),
                ],
            }
        ],
    }
    (repo_root / "corpus.json").write_text(json.dumps(corpus), encoding="utf-8")
    return repo_root


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def test_ac_license_002_clean_scan_returns_complete_result(tmp_path, monkeypatch, capsys):
    repo_root = _build_repo(tmp_path)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", "corpus.json")
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)

    result = license_scanner.scan(COMPONENT_ID, repo_root)

    assert result is not None
    assert field(result, "component_id") == COMPONENT_ID
    assert field(result, "evaluated") is True
    assert field(result, "blocked") is False
    assert list(field(result, "matches")) == []
    score = field(result, "similarity_score")
    assert score is not None
    assert _is_number(score)
    assert score == 0
    threshold = field(result, "block_threshold")
    assert _is_number(threshold)
    assert score < threshold
    assert field(result, "reason") is None

    capsys.readouterr()
    code = license_scanner.main(
        [COMPONENT_ID, "--repo-root=" + str(repo_root), "--format=json"]
    )
    out = capsys.readouterr().out
    assert code == 0
    printed = json.loads(out)
    assert isinstance(printed, dict)

    for name in (
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
    ):
        assert name in printed, name
        expected = field(result, name)
        if name == "matches":
            expected = list(expected)
        assert printed[name] == expected, name

    assert printed["evaluated"] is True
    assert printed["blocked"] is False
    assert printed["matches"] == []
    assert _is_number(printed["similarity_score"])