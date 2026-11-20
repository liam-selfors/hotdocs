# hotdocs-criterion: sha256:b9261fbb28db4058bbccfb9e03348b16959ed4a88ae8df76c3ff667c2218a134
import hashlib
import json
from pathlib import Path

import license_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FOO_SOURCE = (
    "def compute_total(items, factor):\n"
    "    total = 0\n"
    "    for item in items:\n"
    "        total = total + item * factor\n"
    "    return total\n"
    "\n"
    "def describe(name, count):\n"
    "    return name + str(count) + str(compute_total([1, 2, 3], count))\n"
)


def write_fake_cache_manager(repo_root, store_path, log_path):
    src = (
        "import json\n"
        "import dataclasses\n"
        "from dataclasses import dataclass\n"
        "\n"
        "STORE = " + repr(str(store_path)) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "@dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: object = None\n"
        "    gate_inputs_hash: object = None\n"
        "    gate_version: object = None\n"
        "    model_pin: object = None\n"
        "\n"
        "@dataclass\n"
        "class CachedResult:\n"
        "    gate_type: object = None\n"
        "    payload: object = None\n"
        "    stored_at: object = None\n"
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
        "REQUIRED = ['component_id', 'gate_version', 'similarity_score', 'blocked', 'matches']\n"
        "\n"
        "def _key(cache_key):\n"
        "    return json.dumps([cache_key.spec_bundle_hash, cache_key.gate_inputs_hash,\n"
        "                       cache_key.gate_version, cache_key.model_pin], default=str)\n"
        "\n"
        "def _load():\n"
        "    try:\n"
        "        with open(STORE, 'r', encoding='utf-8') as fh:\n"
        "            return json.load(fh)\n"
        "    except (OSError, ValueError):\n"
        "        return {}\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    store = _load()\n"
        "    entry = store.get(_key(cache_key))\n"
        "    if entry is None:\n"
        "        _log('get\\t' + str(cache_key.gate_version) + '\\tmiss')\n"
        "        return Miss()\n"
        "    _log('get\\t' + str(cache_key.gate_version) + '\\thit')\n"
        "    return CachedResult(gate_type=entry['gate_type'], payload=entry['payload'],\n"
        "                        stored_at=entry['stored_at'])\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    gate_type = str(cache_key.gate_version).split('@', 1)[0]\n"
        "    if result.gate_type != gate_type:\n"
        "        raise SchemaValidationError('gate_type mismatch')\n"
        "    payload = result.payload\n"
        "    if dataclasses.is_dataclass(payload) and not isinstance(payload, type):\n"
        "        payload = dataclasses.asdict(payload)\n"
        "    if not isinstance(payload, dict):\n"
        "        raise SchemaValidationError('payload is not a dict')\n"
        "    for name in REQUIRED:\n"
        "        if name not in payload:\n"
        "            raise SchemaValidationError('missing ' + name)\n"
        "    store = _load()\n"
        "    store[_key(cache_key)] = {'gate_type': result.gate_type,\n"
        "                              'payload': json.loads(json.dumps(payload, default=str)),\n"
        "                              'stored_at': result.stored_at}\n"
        "    with open(STORE, 'w', encoding='utf-8') as fh:\n"
        "        json.dump(store, fh)\n"
        "    _log('put\\t' + str(cache_key.gate_version))\n"
    )
    d = repo_root / "gen" / "cache-manager"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cache_manager.py").write_text(src, encoding="utf-8")


def setup_repo(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    foo = repo_root / "gen" / "foo"
    foo.mkdir(parents=True)
    (foo / "foo.py").write_text(FOO_SOURCE, encoding="utf-8")
    store = tmp_path / "store.json"
    log = tmp_path / "cache_log.txt"
    write_fake_cache_manager(repo_root, store, log)
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    return repo_root, log


def read_log(log):
    if not log.exists():
        return []
    return [line.split("\t") for line in log.read_text(encoding="utf-8").splitlines() if line]


def write_corpus(path, entries):
    data = {"corpus_version": 0, "block_threshold": 0.7, "entries": entries}
    path.write_text(json.dumps(data), encoding="utf-8")
    return "license_scanner@4.0.0+" + hashlib.sha256(path.read_bytes()).hexdigest()[:12]


ENTRY_1 = {"reference_id": "ref-001", "license_family": "MIT", "risk_tier": "low",
           "hashes": ["0" * 64]}
ENTRY_2 = {"reference_id": "ref-002", "license_family": "BSD", "risk_tier": "low",
           "hashes": ["1" * 64]}

NOT_EVALUATED_GV = "license_scanner@4.0.0-no-reference-corpus"


def test_not_evaluated_stored_result_not_reused_once_corpus_set(tmp_path, monkeypatch):
    repo_root, log = setup_repo(tmp_path, monkeypatch)

    first = license_scanner.scan("comp-foo", repo_root)
    assert field(first, "evaluated") is False
    assert field(first, "gate_version") == NOT_EVALUATED_GV
    puts = [e for e in read_log(log) if e[0] == "put"]
    assert puts and puts[-1][1] == NOT_EVALUATED_GV

    corpus = repo_root / "corpus.json"
    expected_gv = write_corpus(corpus, [ENTRY_1])
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))

    before = len(read_log(log))
    result = license_scanner.scan("comp-foo", repo_root)
    new_entries = read_log(log)[before:]

    assert field(result, "cache_hit") is False
    assert field(result, "evaluated") is True
    assert field(result, "reason") is None
    assert field(result, "gate_version") == expected_gv
    assert license_scanner.gate_version(repo_root) == expected_gv
    assert not any(e[0] == "get" and e[2] == "hit" for e in new_entries)
    assert ["put", expected_gv] in new_entries


def test_evaluated_stored_result_not_reused_once_corpus_unset(tmp_path, monkeypatch):
    repo_root, log = setup_repo(tmp_path, monkeypatch)
    corpus = repo_root / "corpus.json"
    evaluated_gv = write_corpus(corpus, [ENTRY_1])
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))

    first = license_scanner.scan("comp-foo", repo_root)
    assert field(first, "evaluated") is True
    assert field(first, "gate_version") == evaluated_gv
    puts = [e for e in read_log(log) if e[0] == "put"]
    assert puts and puts[-1][1] == evaluated_gv

    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)

    before = len(read_log(log))
    result = license_scanner.scan("comp-foo", repo_root)
    new_entries = read_log(log)[before:]

    assert field(result, "cache_hit") is False
    assert field(result, "evaluated") is False
    assert field(result, "reason") == "no-reference-corpus"
    assert field(result, "gate_version") == NOT_EVALUATED_GV
    assert field(result, "similarity_score") is None
    assert field(result, "matches") == []
    assert not any(e[0] == "get" and e[2] == "hit" for e in new_entries)


def test_corpus_change_without_version_bump_invalidates_cache(tmp_path, monkeypatch):
    repo_root, log = setup_repo(tmp_path, monkeypatch)
    corpus = repo_root / "corpus.json"
    old_gv = write_corpus(corpus, [ENTRY_1])
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus))

    first = license_scanner.scan("comp-foo", repo_root)
    assert field(first, "evaluated") is True
    assert field(first, "gate_version") == old_gv

    # Control: with nothing changed, the stored result is reused.
    control = license_scanner.scan("comp-foo", repo_root)
    assert field(control, "cache_hit") is True
    assert field(control, "gate_version") == old_gv

    new_gv = write_corpus(corpus, [ENTRY_1, ENTRY_2])
    assert new_gv != old_gv

    before = len(read_log(log))
    result = license_scanner.scan("comp-foo", repo_root)
    new_entries = read_log(log)[before:]

    assert field(result, "cache_hit") is False
    assert field(result, "evaluated") is True
    assert field(result, "gate_version") == new_gv
    assert not any(e[0] == "get" and e[2] == "hit" for e in new_entries)
    assert ["put", new_gv] in new_entries