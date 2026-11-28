# hotdocs-criterion: sha256:aa56241e0865d1c8285e8ef6f76cc221a3d37d98592bf6f31b22ef2bc31b3669
"""AC-LICENSE-007: a clean scan after a flagged one never overwrites the
flagged result; scanning the flagged content again returns the flagged
result from the cache, with the same similarity_score and matches."""

import hashlib
import json
import re
from pathlib import Path

import license_scanner


COMPONENT_ID = "comp-sample"
SLUG = "sample"

FLAGGED_SOURCE = (
    "def alpha_transform(beta, gamma):\n"
    "    delta = beta + gamma\n"
    "    epsilon = delta * 42\n"
    "    zeta = epsilon - beta\n"
    "    eta = zeta + gamma + 7\n"
    "    theta = eta * delta\n"
    "    iota = theta - epsilon + 13\n"
    "    kappa = iota * zeta\n"
    "    lambda_value = kappa + theta + 99\n"
    "    return lambda_value\n"
)

CLEAN_SOURCE = (
    "def unrelated_routine(apple, banana):\n"
    "    cherry = apple\n"
    "    damson = banana\n"
    "    elder = cherry\n"
    "    fig = damson\n"
    "    grape = elder\n"
    "    honeydew = fig\n"
    "    jackfruit = grape\n"
    "    kiwi = honeydew\n"
    "    return kiwi\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def window_hashes(text):
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'""".*?"""', " ", text, flags=re.S)
    text = re.sub(r"'''.*?'''", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r"#[^\n]*", " ", text)
    tokens = [t.lower() for t in re.findall(r"[A-Za-z_][A-Za-z0-9_]*|\d+", text)]
    hashes = set()
    for i in range(len(tokens) - 8):
        joined = "\x1f".join(tokens[i:i + 9])
        hashes.add(hashlib.sha256(joined.encode("utf-8")).hexdigest())
    return sorted(hashes)


def normalize_matches(matches):
    out = []
    for m in matches:
        out.append(
            (
                field(m, "reference_id"),
                field(m, "license_family"),
                field(m, "risk_tier"),
                field(m, "score"),
            )
        )
    return out


def write_fake_cache_manager(repo_root, store_path, log_path):
    base = repo_root / "gen" / "cache-manager"
    base.mkdir(parents=True, exist_ok=True)
    src = (
        "import json\n"
        "import dataclasses\n"
        "from datetime import datetime, timezone\n"
        "from pathlib import Path\n"
        "\n"
        "STORE = Path(" + repr(str(store_path)) + ")\n"
        "LOG = Path(" + repr(str(log_path)) + ")\n"
        "\n"
        "KNOWN = ('generator', 'compiler', 'generated_test', 'llm_judge', 'license_scanner', 'secret_scanner')\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
        "\n"
        "class Miss:\n"
        "    def __eq__(self, other):\n"
        "        return isinstance(other, Miss)\n"
        "    def __hash__(self):\n"
        "        return 0\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str\n"
        "    gate_inputs_hash: str\n"
        "    gate_version: str\n"
        "    model_pin: str\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class CachedResult:\n"
        "    gate_type: str\n"
        "    payload: dict\n"
        "    stored_at: str\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def _load():\n"
        "    if STORE.is_file():\n"
        "        return json.loads(STORE.read_text(encoding='utf-8'))\n"
        "    return {}\n"
        "\n"
        "def _k(cache_key):\n"
        "    return json.dumps([cache_key.spec_bundle_hash, cache_key.gate_inputs_hash, cache_key.gate_version, cache_key.model_pin])\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    store = _load()\n"
        "    entry = store.get(_k(cache_key))\n"
        "    if entry is None:\n"
        "        _log('get miss')\n"
        "        return Miss()\n"
        "    _log('get hit')\n"
        "    return CachedResult(gate_type=entry['gate_type'], payload=entry['payload'], stored_at=entry['stored_at'])\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    gate_type = cache_key.gate_version.split('@', 1)[0]\n"
        "    if result.gate_type not in KNOWN or result.gate_type != gate_type:\n"
        "        raise SchemaValidationError('gate_type mismatch')\n"
        "    for key in ('component_id', 'gate_version', 'similarity_score', 'blocked', 'matches'):\n"
        "        if not isinstance(result.payload, dict) or key not in result.payload:\n"
        "            raise SchemaValidationError('missing ' + key)\n"
        "    store = _load()\n"
        "    store[_k(cache_key)] = {'gate_type': result.gate_type, 'payload': result.payload, 'stored_at': result.stored_at}\n"
        "    STORE.write_text(json.dumps(store), encoding='utf-8')\n"
        "    _log('put')\n"
        "\n"
        "def now_iso():\n"
        "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return {'entry_count': len(_load())}\n"
    )
    (base / "cache_manager.py").write_text(src, encoding="utf-8")


def write_component_source(repo_root, text):
    comp_dir = repo_root / "gen" / SLUG
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "sample.py").write_text(text, encoding="utf-8")


def test_ac_license_007_flagged_result_survives_clean_scan(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    store_path = tmp_path / "fake_cache_store.json"
    log_path = tmp_path / "fake_cache_log.txt"
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
    assert window_hashes(FLAGGED_SOURCE)
    assert not set(window_hashes(CLEAN_SOURCE)) & set(window_hashes(FLAGGED_SOURCE))
    (repo_root / "corpus.json").write_text(json.dumps(corpus), encoding="utf-8")

    monkeypatch.chdir(repo_root)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", "corpus.json")
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    # First scan: flagged content.
    write_component_source(repo_root, FLAGGED_SOURCE)
    first = license_scanner.scan(COMPONENT_ID, repo_root)
    assert field(first, "evaluated") is True
    assert field(first, "blocked") is True
    assert field(first, "cache_hit") is False
    assert field(first, "matches")

    # Second scan: content changed so it scans clean.
    write_component_source(repo_root, CLEAN_SOURCE)
    second = license_scanner.scan(COMPONENT_ID, repo_root)
    assert field(second, "evaluated") is True
    assert field(second, "blocked") is False
    assert field(second, "cache_hit") is False

    # The clean scan added an entry rather than overwriting the flagged one.
    store = json.loads(store_path.read_text(encoding="utf-8"))
    assert len(store) >= 2

    # Third scan: flagged content restored.
    write_component_source(repo_root, FLAGGED_SOURCE)
    third = license_scanner.scan(COMPONENT_ID, repo_root)
    assert field(third, "cache_hit") is True
    assert field(third, "blocked") is True
    assert field(third, "similarity_score") == field(first, "similarity_score")
    assert normalize_matches(field(third, "matches")) == normalize_matches(
        field(first, "matches")
    )

    # The fake confirms the third scan was served by a cache hit.
    log_lines = log_path.read_text(encoding="utf-8").splitlines()
    assert log_lines.count("put") >= 2
    assert log_lines[-1] == "get hit"