# hotdocs-criterion: sha256:f08ea0246bd3d03f2a98e3ab20415a1d36bfb1da68c998e8adfd642535493291
"""AC-SECRET-009: a flagged result stays cached under its own key after a clean rescan."""

import importlib.util
import json
import sys
import urllib.request
from pathlib import Path

import secret_scanner


STORE_ENV = "AC009_CACHE_STORE_PATH"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def fake_cache_manager_source():
    lines = [
        "import dataclasses",
        "import json",
        "import os",
        "from datetime import datetime, timezone",
        "",
        "",
        "@dataclasses.dataclass",
        "class CacheKey:",
        "    spec_bundle_hash: str",
        "    gate_inputs_hash: str",
        "    gate_version: str",
        "    model_pin: str",
        "",
        "",
        "@dataclasses.dataclass",
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
        "def _store_path():",
        "    return os.environ[" + repr(STORE_ENV) + "]",
        "",
        "",
        "def _as_dict(value):",
        "    if dataclasses.is_dataclass(value):",
        "        return dataclasses.asdict(value)",
        "    if isinstance(value, dict):",
        "        return dict(value)",
        "    return dict(vars(value))",
        "",
        "",
        "def _append(record):",
        "    with open(_store_path(), 'a', encoding='utf-8') as fh:",
        "        fh.write(json.dumps(record, sort_keys=True, default=str) + chr(10))",
        "",
        "",
        "def _records():",
        "    path = _store_path()",
        "    if not os.path.exists(path):",
        "        return []",
        "    with open(path, encoding='utf-8') as fh:",
        "        return [json.loads(line) for line in fh if line.strip()]",
        "",
        "",
        "def get(cache_key, *, repo_root=None):",
        "    wanted = json.dumps(_as_dict(cache_key), sort_keys=True, default=str)",
        "    found = None",
        "    for rec in _records():",
        "        if rec.get('op') != 'put':",
        "            continue",
        "        if json.dumps(rec['key'], sort_keys=True, default=str) == wanted:",
        "            found = rec",
        "    _append({'op': 'get', 'key': _as_dict(cache_key)})",
        "    if found is None:",
        "        return Miss()",
        "    return CachedResult(**found['result'])",
        "",
        "",
        "def put(cache_key, result, *, repo_root=None):",
        "    _append({'op': 'put', 'key': _as_dict(cache_key), 'result': _as_dict(result)})",
        "    return None",
        "",
        "",
        "def now_iso():",
        "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')",
        "",
        "",
        "def stats(*, repo_root=None):",
        "    return {'entry_count': len([r for r in _records() if r.get('op') == 'put'])}",
        "",
    ]
    return "\n".join(lines)


def read_records(store_path):
    if not store_path.exists():
        return []
    return [
        json.loads(line)
        for line in store_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def key_text(key):
    return json.dumps(key, sort_keys=True, default=str)


def test_ac_secret_009_flagged_result_survives_clean_rescan(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # Store lives outside repo_root so the scan never sees it.
    store_path = tmp_path / "cache_store.jsonl"

    monkeypatch.setenv(STORE_ENV, str(store_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)

    def no_network(*args, **kwargs):
        raise AssertionError("webhook must not be called without a configured URL")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)

    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    fake_path = cm_dir / "cache_manager.py"
    fake_path.write_text(fake_cache_manager_source(), encoding="utf-8")

    target = repo_root / "gen" / "foo" / "c.py"
    target.parent.mkdir(parents=True)
    target.write_text("K = " + repr("AKIAABCDEFGHIJKLMNOP") + "\n", encoding="utf-8")

    first = secret_scanner.scan(repo_root)
    assert field(first, "flagged") is True

    target.write_text("K = " + repr("") + "\n", encoding="utf-8")

    second = secret_scanner.scan(repo_root)
    assert field(second, "flagged") is False

    puts = [r for r in read_records(store_path) if r.get("op") == "put"]
    assert len(puts) == 2, puts
    first_key, second_key = puts[0]["key"], puts[1]["key"]
    assert key_text(first_key) != key_text(second_key)

    assert field(puts[0]["result"]["payload"], "flagged") is True
    assert field(puts[1]["result"]["payload"], "flagged") is False

    # The flagged result is still retrievable under its own key after the second scan.
    cm = load_module(fake_path, "cache_manager")
    stored = cm.get(cm.CacheKey(**first_key), repo_root=repo_root)
    assert not isinstance(stored, cm.Miss)
    assert field(stored, "gate_type") == "secret_scanner"
    assert field(field(stored, "payload"), "flagged") is True
    assert len(field(field(stored, "payload"), "matches")) >= 1

    clean = cm.get(cm.CacheKey(**second_key), repo_root=repo_root)
    assert not isinstance(clean, cm.Miss)
    assert field(field(clean, "payload"), "flagged") is False