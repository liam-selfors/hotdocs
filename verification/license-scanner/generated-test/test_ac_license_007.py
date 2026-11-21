# hotdocs-criterion: sha256:046248f5e5b611b469372d4818a6e8ccc5bcfd97a78e483d881faf00fde0a832
import hashlib
import json
import re

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def window_hashes(text):
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]
    out = set()
    for i in range(len(tokens) - 8):
        joined = "\x1f".join(tokens[i:i + 9])
        out.add(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return sorted(out)


FLAGGED_SOURCE = (
    "def copied_routine(alpha, beta, gamma):\n"
    "    total = alpha + beta + gamma\n"
    "    for index in range(total):\n"
    "        total = total * index + alpha - beta\n"
    "    return total + gamma * 42\n"
)

CLEAN_SOURCE = (
    "def original_helper(width, height, depth):\n"
    "    volume = width * height * depth\n"
    "    while volume > 1000:\n"
    "        volume = volume // 7 + height\n"
    "    return volume - depth + 99\n"
)


def write_fake_cache_manager(repo_root, store_path, log_path):
    base = repo_root / "gen" / "cache-manager"
    base.mkdir(parents=True, exist_ok=True)
    src = (
        "import json\n"
        "import os\n"
        "from dataclasses import dataclass\n"
        "from datetime import datetime, timezone\n"
        "\n"
        "STORE = " + repr(str(store_path)) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "@dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str\n"
        "    gate_inputs_hash: str\n"
        "    gate_version: str\n"
        "    model_pin: str\n"
        "\n"
        "@dataclass\n"
        "class CachedResult:\n"
        "    gate_type: str\n"
        "    payload: dict\n"
        "    stored_at: str\n"
        "\n"
        "class Miss:\n"
        "    def __eq__(self, other):\n"
        "        return isinstance(other, Miss)\n"
        "    def __hash__(self):\n"
        "        return 0\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
        "\n"
        "def _load():\n"
        "    if os.path.exists(STORE):\n"
        "        with open(STORE) as fh:\n"
        "            return json.load(fh)\n"
        "    return {}\n"
        "\n"
        "def _k(key):\n"
        "    return json.dumps([key.spec_bundle_hash, key.gate_inputs_hash, key.gate_version, key.model_pin])\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _log('get')\n"
        "    data = _load()\n"
        "    entry = data.get(_k(cache_key))\n"
        "    if entry is None:\n"
        "        return Miss()\n"
        "    return CachedResult(gate_type=entry['gate_type'], payload=entry['payload'], stored_at=entry['stored_at'])\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _log('put')\n"
        "    payload = result.payload if isinstance(result.payload, dict) else dict(vars(result.payload))\n"
        "    data = _load()\n"
        "    data[_k(cache_key)] = {'gate_type': result.gate_type, 'payload': payload, 'stored_at': result.stored_at}\n"
        "    with open(STORE, 'w') as fh:\n"
        "        json.dump(data, fh, default=str)\n"
        "    return None\n"
        "\n"
        "def now_iso():\n"
        "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return {'entry_count': len(_load())}\n"
    )
    (base / "cache_manager.py").write_text(src)


def test_flagged_result_is_kept_alongside_later_clean_result(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    store_path = tmp_path / "fake_store.json"
    log_path = tmp_path / "fake_log.txt"
    write_fake_cache_manager(repo_root, store_path, log_path)

    corpus = {
        "corpus_version": 3,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": window_hashes(FLAGGED_SOURCE),
            }
        ],
    }
    (repo_root / "corpus.json").write_text(json.dumps(corpus))
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", "corpus.json")
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)

    comp_dir = repo_root / "gen" / "foo"
    comp_dir.mkdir(parents=True)
    source_file = comp_dir / "foo.py"

    # First generation sample: flagged.
    source_file.write_text(FLAGGED_SOURCE)
    flagged = license_scanner.scan("comp-foo", repo_root)
    assert field(flagged, "evaluated") is True
    assert field(flagged, "blocked") is True
    flagged_snapshot = {
        "blocked": field(flagged, "blocked"),
        "similarity_score": field(flagged, "similarity_score"),
        "matches": list(field(flagged, "matches")),
    }
    assert flagged_snapshot["matches"]

    # Retried sample: clean.
    source_file.write_text(CLEAN_SOURCE)
    clean = license_scanner.scan("comp-foo", repo_root)
    assert field(clean, "evaluated") is True
    assert field(clean, "blocked") is False

    # The original flagged result object is not altered by the clean scan.
    assert field(flagged, "blocked") is True
    assert field(flagged, "similarity_score") == flagged_snapshot["similarity_score"]
    assert list(field(flagged, "matches")) == flagged_snapshot["matches"]

    # Fake cache-manager actually ran.
    assert log_path.is_file()
    assert "put" in log_path.read_text().splitlines()

    # Both records are present: the clean one did not overwrite the flagged one.
    store = json.loads(store_path.read_text())
    payloads = [entry["payload"] for entry in store.values()]
    blocked_values = sorted(bool(p["blocked"]) for p in payloads if p.get("component_id") == "comp-foo")
    assert True in blocked_values, "flagged record was deleted or overwritten"
    assert False in blocked_values, "clean record missing"
    assert len(store) >= 2

    # The flagged record is still retrievable: re-scanning the flagged sample
    # yields the flagged result again.
    source_file.write_text(FLAGGED_SOURCE)
    again = license_scanner.scan("comp-foo", repo_root)
    assert field(again, "blocked") is True
    assert field(again, "similarity_score") == flagged_snapshot["similarity_score"]
    assert field(again, "cache_hit") is True