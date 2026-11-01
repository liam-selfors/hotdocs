import json

import license_scanner


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _write_corpus(path, corpus_version):
    data = {"corpus_version": corpus_version, "block_threshold": 0.70, "entries": []}
    path.write_text(json.dumps(data))


def _write_scanned_component_files(repo_root, slug):
    comp_dir = repo_root / "gen" / slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "widget.py").write_text("def total(a, b):\n    return a + b\n")


def _write_cache_manager_fake(repo_root, log_path):
    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True, exist_ok=True)
    module_path = cache_dir / "cache_manager.py"
    module_path.write_text(
        "import dataclasses\n"
        "\n"
        f"LOG_PATH = {str(log_path)!r}\n"
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
        "    payload: object\n"
        "    stored_at: str\n"
        "\n"
        "def _record(name):\n"
        "    with open(LOG_PATH, 'a') as f:\n"
        "        f.write(name + chr(10))\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _record('get')\n"
        "    return CachedResult(gate_type='license_scanner', payload=None, stored_at='1970-01-01T00:00:00Z')\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _record('put')\n"
        "    return None\n"
    )


def test_gate_version_matches_scan_and_tracks_corpus_version(tmp_path, monkeypatch):
    repo_root = tmp_path
    corpus_path = repo_root / "corpus.json"
    _write_corpus(corpus_path, 4)
    monkeypatch.setenv("VAR_LICENSE_CORPUS_PATH", str(corpus_path))

    component_id = "comp-acme-widget"
    _write_scanned_component_files(repo_root, "acme-widget")

    log_path = repo_root / "cache_calls.log"
    _write_cache_manager_fake(repo_root, log_path)

    gv = license_scanner.gate_version(repo_root)
    result = license_scanner.scan(component_id, repo_root)
    scan_gv = _get(result, "gate_version")

    assert isinstance(gv, str)
    assert gv == scan_gv
    assert gv == "license_scanner@3.1.4"

    _write_corpus(corpus_path, 5)
    gv_after = license_scanner.gate_version(repo_root)

    assert gv_after != gv
    assert gv_after == "license_scanner@3.1.5"


def test_gate_version_matches_scan_without_corpus_var(tmp_path, monkeypatch):
    repo_root = tmp_path
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)

    component_id = "comp-beta-gadget"
    _write_scanned_component_files(repo_root, "beta-gadget")

    log_path = repo_root / "cache_calls.log"
    _write_cache_manager_fake(repo_root, log_path)

    gv = license_scanner.gate_version(repo_root)
    result = license_scanner.scan(component_id, repo_root)
    scan_gv = _get(result, "gate_version")

    assert isinstance(gv, str)
    assert gv == scan_gv
    assert gv == "license_scanner@3.1.0"


def test_gate_version_never_touches_cache_manager_without_gen_dir(tmp_path, monkeypatch):
    repo_root = tmp_path
    monkeypatch.delenv("VAR_LICENSE_CORPUS_PATH", raising=False)

    log_path = repo_root / "cache_calls.log"
    _write_cache_manager_fake(repo_root, log_path)

    gv = license_scanner.gate_version(repo_root)

    assert isinstance(gv, str)
    assert not log_path.exists()