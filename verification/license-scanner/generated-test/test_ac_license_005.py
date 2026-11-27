# hotdocs-criterion: sha256:70e7637818d6057a669dcb18ec8b77bdd92fa51c2dd7b99bc6da20305eb8358f
"""AC-LICENSE-005: a cached result under an old corpus's gate_version is never
reused once the reference corpus changes; a fresh scan is performed instead.

The criterion's "license_scanner@1.0.0" -> "license_scanner@2.0.0" is modelled
by a reference corpus whose `corpus_version` goes from 1 to 2, so that, per
R-LICENSE-005, the gate_version on the scan goes from
`license_scanner@4.0.1+<H1>` to `license_scanner@4.0.2+<H2>`.
"""

import hashlib
import json
from pathlib import Path

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SOURCE = (
    "def compute_totals(items, factor, offset, limit, scale):\n"
    "    total = 0\n"
    "    for item in items:\n"
    "        total = total + item * factor + offset\n"
    "        if total > limit:\n"
    "            total = limit\n"
    "    return total * scale\n"
)


def _fake_cache_manager_source(log_path, store_path):
    return (
        "import dataclasses\n"
        "import json\n"
        "from pathlib import Path\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "STORE = " + repr(str(store_path)) + "\n"
        "\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
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
        "def _log(line):\n"
        "    with open(LOG, 'a') as f:\n"
        "        f.write(line + '\\n')\n"
        "\n"
        "\n"
        "def _key(k):\n"
        "    return json.dumps([str(k.spec_bundle_hash), str(k.gate_inputs_hash),\n"
        "                       str(k.gate_version), str(k.model_pin)])\n"
        "\n"
        "\n"
        "def _load():\n"
        "    p = Path(STORE)\n"
        "    return json.loads(p.read_text()) if p.is_file() else dict()\n"
        "\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _log('get\\t' + str(cache_key.gate_version))\n"
        "    entry = _load().get(_key(cache_key))\n"
        "    if entry is None:\n"
        "        return Miss()\n"
        "    return CachedResult(gate_type=entry['gate_type'], payload=entry['payload'],\n"
        "                        stored_at=entry['stored_at'])\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _log('put\\t' + str(cache_key.gate_version))\n"
        "    gate_type = str(cache_key.gate_version).split('@')[0]\n"
        "    if result.gate_type != gate_type:\n"
        "        raise SchemaValidationError('gate_type mismatch')\n"
        "    payload = result.payload\n"
        "    for name in ('component_id', 'gate_version', 'similarity_score', 'blocked', 'matches'):\n"
        "        if name not in payload:\n"
        "            raise SchemaValidationError('missing payload key ' + name)\n"
        "    data = _load()\n"
        "    data[_key(cache_key)] = dict(gate_type=result.gate_type, payload=payload,\n"
        "                                 stored_at=result.stored_at)\n"
        "    Path(STORE).write_text(json.dumps(data, default=str))\n"
        "\n"
        "\n"
        "def now_iso():\n"
        "    import datetime\n"
        "    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return dict(entry_count=len(_load()))\n"
    )


def _build_repo(repo_root, log_path, store_path):
    # Fake cache-manager, flat-module shape.
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(
        _fake_cache_manager_source(log_path, store_path)
    )

    # Minimal fixture spec for comp-foo (sealed, short fake source_path).
    comp = repo_root / "specs" / "components" / "foo"
    (comp / "requirements").mkdir(parents=True)
    (comp / "acceptance").mkdir(parents=True)
    (comp / "interface").mkdir(parents=True)
    (comp / "component.md").write_text(
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
        "A fixture component.\n"
    )
    (comp / "requirements" / "R-FOO-001.md").write_text(
        "# R-FOO-001\n\n**R-FOO-001** — Foo MUST compute totals.\n"
    )
    (comp / "acceptance" / "AC-FOO-001.md").write_text(
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n"
    )
    (comp / "interface" / "library.md").write_text(
        "# Library\n\n```\ncompute_totals(items, factor, offset, limit, scale) -> int\n```\n"
    )
    (comp / "constraints.md").write_text("# Constraints\n\nNone.\n")
    (repo_root / "specs" / "glossary.md").write_text("# Glossary\n\n- **Foo** — a fixture.\n")

    # Component source, in both plausible locations.
    for d in (repo_root / "gen" / "foo", repo_root / "legacy" / "foo"):
        d.mkdir(parents=True, exist_ok=True)
        (d / "foo.py").write_text(SOURCE)


def _write_corpus(path, corpus_version):
    corpus = {
        "corpus_version": corpus_version,
        "block_threshold": 0.70,
        "entries": [
            {
                "reference_id": "ref-001",
                "license_family": "GPL",
                "risk_tier": "high",
                "hashes": [hashlib.sha256(b"unrelated-window").hexdigest()],
            }
        ],
    }
    path.write_text(json.dumps(corpus, indent=2))
    return "license_scanner@4.0." + str(corpus_version) + "+" + hashlib.sha256(
        path.read_bytes()
    ).hexdigest()[:12]


def _log_lines(log_path):
    if not log_path.is_file():
        return []
    return [line for line in log_path.read_text().splitlines() if line]


def test_ac_license_005_stale_cache_entry_not_reused_after_corpus_update(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "cache_calls.log"
    store_path = tmp_path / "cache_store.json"
    _build_repo(repo_root, log_path, store_path)

    corpus_path = repo_root / "corpus.json"
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", "corpus.json")
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)

    # --- Given: a result cached under the old corpus's gate_version. ---
    old_gv = _write_corpus(corpus_path, 1)
    assert license_scanner.gate_version(repo_root) == old_gv

    first = license_scanner.scan("comp-foo", repo_root)
    assert field(first, "evaluated") is True
    assert field(first, "gate_version") == old_gv
    assert ("put\t" + old_gv) in _log_lines(log_path), _log_lines(log_path)

    # Sanity: with the corpus unchanged, the cache entry IS reused, so the
    # later miss is meaningful.
    puts_before = sum(1 for l in _log_lines(log_path) if l.startswith("put\t"))
    again = license_scanner.scan("comp-foo", repo_root)
    assert field(again, "cache_hit") is True
    assert field(again, "gate_version") == old_gv
    puts_after = sum(1 for l in _log_lines(log_path) if l.startswith("put\t"))
    assert puts_after == puts_before

    # --- When: the reference corpus is updated and license-scan runs again. ---
    new_gv = _write_corpus(corpus_path, 2)
    assert new_gv != old_gv
    assert license_scanner.gate_version(repo_root) == new_gv

    log_len_before = len(_log_lines(log_path))
    second = license_scanner.scan("comp-foo", repo_root)
    new_calls = _log_lines(log_path)[log_len_before:]

    # --- Then: the stale entry is not reused; a fresh scan is performed. ---
    assert field(second, "cache_hit") is False
    assert field(second, "evaluated") is True
    assert field(second, "gate_version") == new_gv
    assert field(second, "gate_version") != old_gv

    # The lookup used the new gate_version, never the stale one.
    get_versions = [l.split("\t", 1)[1] for l in new_calls if l.startswith("get\t")]
    assert get_versions, new_calls
    assert all(v == new_gv for v in get_versions), new_calls

    # A fresh result was computed and stored under the new gate_version.
    assert ("put\t" + new_gv) in new_calls, new_calls
    assert ("put\t" + old_gv) not in new_calls, new_calls