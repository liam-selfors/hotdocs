import json
import os

import license_scanner


def get_field(obj, name, default=None):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def make_entry(ref_id="ref-1", risk_tier="low"):
    return {
        "reference_id": ref_id,
        "license_family": "GPL",
        "risk_tier": risk_tier,
        "hashes": ["deadbeefcafebabe"],
    }


def write_corpus(path, corpus_version, entries, block_threshold=0.7):
    data = {
        "corpus_version": corpus_version,
        "block_threshold": block_threshold,
        "entries": entries,
    }
    path.write_text(json.dumps(data))


def create_component(repo_root, slug):
    comp_dir = repo_root / "gen" / slug
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / (slug + ".py")).write_text(
        "def sample_function(argument_one, argument_two):\n"
        "    total = argument_one + argument_two\n"
        "    return total\n"
    )


FAKE_CACHE_MANAGER_TEMPLATE = '''
LOG_PATH = %(log_path)r


def _record(name):
    with open(LOG_PATH, "a") as f:
        f.write(name + "\\n")


class CacheKey:
    def __init__(self, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):
        self.spec_bundle_hash = spec_bundle_hash
        self.gate_inputs_hash = gate_inputs_hash
        self.gate_version = gate_version
        self.model_pin = model_pin


class CachedResult:
    def __init__(self, gate_type, payload, stored_at):
        self.gate_type = gate_type
        self.payload = payload
        self.stored_at = stored_at


class Miss:
    pass


def get(cache_key, *, repo_root=None):
    _record("get")
    return Miss()


def put(cache_key, result, *, repo_root=None):
    _record("put")
    return None
'''


def test_gate_version_matches_scan_result_for_usable_corpus(tmp_path):
    repo_root = tmp_path / "repo1"
    repo_root.mkdir()
    create_component(repo_root, "foo")
    corpus_path = repo_root / "corpus.json"
    write_corpus(corpus_path, 4, [make_entry()])

    os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)
    os.environ["VAR_LICENSE_CORPUS_PATH"] = str(corpus_path)
    try:
        gv = license_scanner.gate_version(repo_root)
        result = license_scanner.scan("comp-foo", repo_root)
        result_gv = get_field(result, "gate_version")
        assert isinstance(gv, str)
        assert gv == result_gv
    finally:
        os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)


def test_gate_version_changes_when_corpus_changes(tmp_path):
    base_entry = make_entry()

    repo_a = tmp_path / "repo2a"
    repo_a.mkdir()
    corpus_a = repo_a / "corpus.json"
    write_corpus(corpus_a, 4, [base_entry])

    repo_b = tmp_path / "repo2b"
    repo_b.mkdir()
    corpus_b = repo_b / "corpus.json"
    write_corpus(corpus_b, 4, [base_entry])

    os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)
    try:
        os.environ["VAR_LICENSE_CORPUS_PATH"] = str(corpus_a)
        baseline_a = license_scanner.gate_version(repo_a)
        write_corpus(corpus_a, 5, [base_entry])
        bumped = license_scanner.gate_version(repo_a)
        assert bumped != baseline_a

        os.environ["VAR_LICENSE_CORPUS_PATH"] = str(corpus_b)
        baseline_b = license_scanner.gate_version(repo_b)
        write_corpus(corpus_b, 4, [base_entry, make_entry(ref_id="ref-2")])
        entry_added = license_scanner.gate_version(repo_b)
        assert entry_added != baseline_b
    finally:
        os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)


def test_gate_version_matches_scan_across_unusable_corpus_states(tmp_path):
    repo_root = tmp_path / "repo3"
    repo_root.mkdir()
    create_component(repo_root, "bar")

    results = []

    os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)
    try:
        gv_unset = license_scanner.gate_version(repo_root)
        scan_unset = license_scanner.scan("comp-bar", repo_root)
        assert gv_unset == get_field(scan_unset, "gate_version")
        results.append(gv_unset)

        missing_path = repo_root / "does-not-exist.json"
        os.environ["VAR_LICENSE_CORPUS_PATH"] = str(missing_path)
        gv_missing = license_scanner.gate_version(repo_root)
        scan_missing = license_scanner.scan("comp-bar", repo_root)
        assert gv_missing == get_field(scan_missing, "gate_version")
        results.append(gv_missing)

        invalid_path = repo_root / "invalid.json"
        invalid_path.write_text(json.dumps({"entries": "not-a-list"}))
        os.environ["VAR_LICENSE_CORPUS_PATH"] = str(invalid_path)
        gv_invalid = license_scanner.gate_version(repo_root)
        scan_invalid = license_scanner.scan("comp-bar", repo_root)
        assert gv_invalid == get_field(scan_invalid, "gate_version")
        results.append(gv_invalid)
    finally:
        os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)

    assert len(results) == 3
    assert len(set(results)) == 3


def test_gate_version_never_calls_cache_manager_and_needs_no_gen(tmp_path):
    repo_root = tmp_path / "repo4"
    repo_root.mkdir()

    cache_manager_dir = repo_root / "gen" / "cache-manager"
    cache_manager_dir.mkdir(parents=True)
    log_path = tmp_path / "cache_manager_calls.log"
    fake_source = FAKE_CACHE_MANAGER_TEMPLATE % {"log_path": str(log_path)}
    (cache_manager_dir / "cache_manager.py").write_text(fake_source)

    os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)
    try:
        gv = license_scanner.gate_version(repo_root)
    finally:
        os.environ.pop("VAR_LICENSE_CORPUS_PATH", None)

    assert isinstance(gv, str)
    assert not log_path.exists()