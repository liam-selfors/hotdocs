# hotdocs-criterion: sha256:b570ca1a50686698028af3fa2c8472224493e8f2690b2406b216e26c812ce350
import importlib.util
import json
import os
import sys
import urllib.request
from pathlib import Path

import secret_scanner


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


LOG_ENV = "SECRET_SCANNER_TEST_CACHE_LOG"


def _fake_cache_manager_source():
    lines = [
        "import os",
        "import time",
        "from dataclasses import dataclass",
        "from pathlib import Path",
        "",
        "",
        "def _log(line):",
        "    p = os.environ.get(" + repr(LOG_ENV) + ")",
        "    if p:",
        "        with open(p, 'a', encoding='utf-8') as fh:",
        "            fh.write(line + '\\n')",
        "",
        "",
        "class SchemaValidationError(ValueError):",
        "    pass",
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
        "_REQUIRED = " + repr({"secret_scanner": ["scope", "gate_version", "flagged", "matches"]}),
        "",
        "",
        "def get(cache_key, *, repo_root=None):",
        "    _log('get')",
        "    return Miss()",
        "",
        "",
        "def put(cache_key, result, *, repo_root=None):",
        "    _log('put')",
        "    gate_type = result['gate_type'] if isinstance(result, dict) else result.gate_type",
        "    payload = result['payload'] if isinstance(result, dict) else result.payload",
        "    key_gate_version = cache_key['gate_version'] if isinstance(cache_key, dict) else cache_key.gate_version",
        "    if str(key_gate_version).split('@')[0] != gate_type:",
        "        raise SchemaValidationError('gate_type mismatch')",
        "    for k in _REQUIRED.get(gate_type, []):",
        "        if not isinstance(payload, dict) or k not in payload:",
        "            raise SchemaValidationError('missing key ' + k)",
        "    return None",
        "",
        "",
        "def now_iso():",
        "    return time.strftime(" + repr("%Y-%m-%dT%H:%M:%SZ") + ", time.gmtime())",
        "",
        "",
        "def stats(*, repo_root=None):",
        "    return " + repr({"entry_count": 0}),
        "",
    ]
    return "\n".join(lines)


def test_clean_full_scan_returns_complete_unflagged_result(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    # A clean repository: plain, harmless content only.
    (repo_root / "README.md").write_text("# Clean project\n\nNothing to see here.\n", encoding="utf-8")
    src = repo_root / "src"
    src.mkdir()
    (src / "app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    # Fake cache-manager so the scan never sees a cached result.
    cm_dir = repo_root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(_fake_cache_manager_source(), encoding="utf-8")

    log_path = tmp_path / "cache_log.txt"
    monkeypatch.setenv(LOG_ENV, str(log_path))
    monkeypatch.delenv("VAR_COMPLIANCE_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)

    def _no_network(*args, **kwargs):
        raise AssertionError("webhook must not be called for a clean scan")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)

    result = secret_scanner.scan(repo_root)

    assert result is not None
    assert not isinstance(result, dict)

    assert field(result, "flagged") is False
    matches = field(result, "matches")
    assert matches is not None
    assert list(matches) == []

    d = result.to_dict()
    assert isinstance(d, dict)
    assert d
    assert "flagged" in d
    assert "matches" in d
    assert d["flagged"] is False
    assert d["matches"] == []

    # The dict is the JSON shape: it must serialize cleanly.
    roundtrip = json.loads(json.dumps(d))
    assert roundtrip["flagged"] is False
    assert roundtrip["matches"] == []