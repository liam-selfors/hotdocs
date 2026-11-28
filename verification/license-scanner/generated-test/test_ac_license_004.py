# hotdocs-criterion: sha256:d64511ccb54c0b0442a77f03ea657c3e60d3e83fe32a0a5cf3efd12a7394e8b1
"""AC-LICENSE-004: on a cache hit for the exact key, the cached result is
returned and no rescan is performed (R-LICENSE-004)."""

import json
from pathlib import Path

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SOURCE_TEXT = (
    "def compute_total(items, tax_rate, discount):\n"
    "    subtotal = sum(item.price for item in items)\n"
    "    taxed = subtotal * (1 + tax_rate)\n"
    "    return taxed - discount\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-foo]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST compute a total.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven items\nWhen totaled\nThen a total is returned\n```\n",
    )
    _write(comp / "interface" / "library.md", "# Library\n\n```\ncompute_total(items, tax_rate, discount)\n```\n")
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a fixture.\n")

    # Source in both plausible locations (generated output and sealed source path).
    _write(repo_root / "gen" / "foo" / "foo.py", SOURCE_TEXT)
    _write(repo_root / "legacy" / "foo" / "foo.py", SOURCE_TEXT)

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
    _write(corpus_path, json.dumps(corpus))
    return corpus_path


def _write_fake_cache_manager(repo_root, log_path, store_path):
    lines = [
        "import json",
        "from dataclasses import dataclass",
        "",
        "LOG = " + repr(str(log_path)),
        "STORE = " + repr(str(store_path)),
        "",
        "",
        "@dataclass",
        "class CacheKey:",
        "    spec_bundle_hash: str",
        "    gate_inputs_hash: str",
        "    gate_version: str",
        "    model_pin: str",
        "",
        "",
        "@dataclass",
        "class CachedResult:",
        "    gate_type: str",
        "    payload: dict",
        "    stored_at: str",
        "",
        "",
        "class Miss:",
        "    def __eq__(self, other):",
        "        return isinstance(other, Miss)",
        "",
        "    def __hash__(self):",
        "        return 0",
        "",
        "",
        "class SchemaValidationError(ValueError):",
        "    pass",
        "",
        "",
        "def _key(cache_key):",
        "    return json.dumps([cache_key.spec_bundle_hash, cache_key.gate_inputs_hash,",
        "                       cache_key.gate_version, cache_key.model_pin], default=str)",
        "",
        "",
        "def _log(kind, key):",
        "    with open(LOG, 'a', encoding='utf-8') as fh:",
        "        fh.write(json.dumps([kind, key]) + '\\n')",
        "",
        "",
        "def _load():",
        "    try:",
        "        with open(STORE, 'r', encoding='utf-8') as fh:",
        "            return json.load(fh)",
        "    except (OSError, ValueError):",
        "        return dict()",
        "",
        "",
        "def _plain(o):",
        "    if hasattr(o, '__dict__'):",
        "        return vars(o)",
        "    return str(o)",
        "",
        "",
        "def get(cache_key, *, repo_root=None):",
        "    key = _key(cache_key)",
        "    _log('get', key)",
        "    store = _load()",
        "    if key in store:",
        "        entry = store[key]",
        "        return CachedResult(gate_type=entry['gate_type'], payload=entry['payload'],",
        "                            stored_at=entry['stored_at'])",
        "    return Miss()",
        "",
        "",
        "def put(cache_key, result, *, repo_root=None):",
        "    key = _key(cache_key)",
        "    _log('put', key)",
        "    store = _load()",
        "    payload = json.loads(json.dumps(result.payload, default=_plain))",
        "    store[key] = dict(gate_type=result.gate_type, payload=payload,",
        "                      stored_at=result.stored_at)",
        "    with open(STORE, 'w', encoding='utf-8') as fh:",
        "        json.dump(store, fh)",
        "",
    ]
    _write(repo_root / "gen" / "cache-manager" / "cache_manager.py", "\n".join(lines))


def _read_log(log_path):
    if not log_path.is_file():
        return []
    return [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_cache_hit_returns_cached_result_without_rescan(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    log_path = work / "cache_calls.log"
    store_path = work / "cache_store.json"

    corpus_path = _build_fixture(repo_root)
    _write_fake_cache_manager(repo_root, log_path, store_path)

    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)

    # Phase 1: cold cache -> fresh scan, stored via put under the scanner's own key.
    first = license_scanner.scan("comp-foo", repo_root)
    calls = _read_log(log_path)
    puts = [k for kind, k in calls if kind == "put"]
    gets = [k for kind, k in calls if kind == "get"]
    assert len(gets) >= 1, calls
    assert len(puts) == 1, calls
    key = puts[0]
    assert gets[0] == key, "lookup key must be the same key the result is stored under"

    expected_gate_version = license_scanner.gate_version(repo_root)
    assert json.loads(key)[2] == expected_gate_version
    assert field(first, "gate_version") == expected_gate_version

    # Replace the stored payload with a distinctive sentinel that no real scan
    # of this fixture could produce: returning it proves no rescan happened.
    store = json.loads(store_path.read_text(encoding="utf-8"))
    assert key in store
    sentinel_payload = dict(store[key]["payload"])
    sentinel_payload.update(
        {
            "component_id": "comp-foo",
            "gate_version": expected_gate_version,
            "evaluated": True,
            "reason": None,
            "similarity_score": 0.0123,
            "block_threshold": 0.70,
            "blocked": False,
            "matches": [
                {
                    "reference_id": "ref-cached-sentinel",
                    "license_family": "sentinel",
                    "risk_tier": "low",
                    "score": 0.0123,
                }
            ],
            "notified": False,
            "notification_delivery_error": None,
        }
    )
    store[key]["payload"] = sentinel_payload
    store_path.write_text(json.dumps(store), encoding="utf-8")
    log_path.write_text("", encoding="utf-8")

    # Phase 2: matching inputs -> cache hit for the exact key.
    second = license_scanner.scan("comp-foo", repo_root)
    calls2 = _read_log(log_path)
    gets2 = [k for kind, k in calls2 if kind == "get"]
    puts2 = [k for kind, k in calls2 if kind == "put"]

    assert gets2 and gets2[0] == key, calls2
    assert puts2 == [], "a cache hit must not trigger a fresh scan and re-store"

    assert field(second, "similarity_score") == 0.0123
    matches = field(second, "matches")
    assert len(matches) == 1
    assert field(matches[0], "reference_id") == "ref-cached-sentinel"
    assert field(second, "component_id") == "comp-foo"
    assert field(second, "gate_version") == expected_gate_version
    assert field(second, "blocked") is False