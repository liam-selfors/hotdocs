# hotdocs-criterion: sha256:94d46df8610db6edbb8312679ddd5f626fb4262ba7128ca6b80701b52008d07d
"""AC-CACHE-002: the same four key components supplied by two different
calling components produce byte-identical serialized cache keys.

The key-formation logic is cache_manager's own responsibility, so the
test checks it through the public interface. Two separately loaded
"caller" modules each build a CacheKey their own way from equal but
distinct component values, then put and get through cache_manager. If
the serialized keys are byte-identical, both callers address one and the
same store entry. That means:

- a put by one caller is a hit for the other;
- a put by both leaves exactly one entry, last write wins;
- the CLI `inspect` with the same four values hits that entry.
"""

import importlib.util
import json
import sys

import cache_manager


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


SPEC_BUNDLE_HASH = "sha256:" + "a1" * 32
GATE_INPUTS_HASH = "sha256:" + "b2" * 32
GATE_VERSION = "license_scanner@4.0.3+9f2c41ab07de"
MODEL_PIN = "claude-sonnet-5"


# Caller A: builds the key by keyword in the documented field order.
CALLER_A_SOURCE = (
    "import cache_manager\n"
    "\n"
    "def make_key(spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):\n"
    "    return cache_manager.CacheKey(\n"
    "        spec_bundle_hash=spec_bundle_hash,\n"
    "        gate_inputs_hash=gate_inputs_hash,\n"
    "        gate_version=gate_version,\n"
    "        model_pin=model_pin,\n"
    "    )\n"
    "\n"
    "def store(repo_root, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin, payload, stored_at):\n"
    "    key = make_key(spec_bundle_hash, gate_inputs_hash, gate_version, model_pin)\n"
    "    result = cache_manager.CachedResult(\n"
    "        gate_type=gate_version.split('@')[0],\n"
    "        payload=payload,\n"
    "        stored_at=stored_at,\n"
    "    )\n"
    "    cache_manager.put(key, result, repo_root=repo_root)\n"
    "\n"
    "def fetch(repo_root, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):\n"
    "    key = make_key(spec_bundle_hash, gate_inputs_hash, gate_version, model_pin)\n"
    "    return cache_manager.get(key, repo_root=repo_root)\n"
)

# Caller B: builds the key from a dict of kwargs in a different order,
# with freshly constructed (equal but distinct) string objects.
CALLER_B_SOURCE = (
    "import cache_manager\n"
    "\n"
    "def make_key(spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):\n"
    "    parts = dict()\n"
    "    parts['model_pin'] = ''.join(list(model_pin))\n"
    "    parts['gate_version'] = ''.join(list(gate_version))\n"
    "    parts['gate_inputs_hash'] = ''.join(list(gate_inputs_hash))\n"
    "    parts['spec_bundle_hash'] = ''.join(list(spec_bundle_hash))\n"
    "    return cache_manager.CacheKey(**parts)\n"
    "\n"
    "def store(repo_root, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin, payload, stored_at):\n"
    "    key = make_key(spec_bundle_hash, gate_inputs_hash, gate_version, model_pin)\n"
    "    result = cache_manager.CachedResult(\n"
    "        gate_type=gate_version.partition('@')[0],\n"
    "        payload=payload,\n"
    "        stored_at=stored_at,\n"
    "    )\n"
    "    cache_manager.put(key, result, repo_root=repo_root)\n"
    "\n"
    "def fetch(repo_root, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):\n"
    "    key = make_key(spec_bundle_hash, gate_inputs_hash, gate_version, model_pin)\n"
    "    return cache_manager.get(key, repo_root=repo_root)\n"
)


def _payload(component_id, score):
    return {
        "component_id": component_id,
        "gate_version": GATE_VERSION,
        "similarity_score": score,
        "blocked": False,
        "matches": [],
    }


def _load_callers(tmp_path):
    callers_dir = tmp_path / "callers"
    callers_dir.mkdir()
    a_path = callers_dir / "ac_cache_002_caller_a.py"
    b_path = callers_dir / "ac_cache_002_caller_b.py"
    a_path.write_text(CALLER_A_SOURCE)
    b_path.write_text(CALLER_B_SOURCE)
    caller_a = load_module(str(a_path), "ac_cache_002_caller_a")
    caller_b = load_module(str(b_path), "ac_cache_002_caller_b")
    return caller_a, caller_b


def _components():
    return (SPEC_BUNDLE_HASH, GATE_INPUTS_HASH, GATE_VERSION, MODEL_PIN)


def test_two_callers_with_same_components_share_one_key(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    cwd_a = tmp_path / "cwd_a"
    cwd_b = tmp_path / "cwd_b"
    cwd_a.mkdir()
    cwd_b.mkdir()

    caller_a, caller_b = _load_callers(tmp_path)

    # The two callers' key objects are equal.
    key_a = caller_a.make_key(*_components())
    key_b = caller_b.make_key(*_components())
    assert key_a == key_b

    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 0

    # Caller A puts. Caller B, from a different cwd, gets a hit on the same entry.
    monkeypatch.chdir(cwd_a)
    caller_a.store(repo_root, *_components(), _payload("comp-a", 0.1), "2026-10-02T00:00:00Z")
    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 1

    monkeypatch.chdir(cwd_b)
    got_b = caller_b.fetch(repo_root, *_components())
    assert not isinstance(got_b, cache_manager.Miss)
    assert field(got_b, "gate_type") == "license_scanner"
    assert field(field(got_b, "payload"), "component_id") == "comp-a"

    # Caller B puts under its own key. If the serialized keys are
    # byte-identical, B overwrites A's entry instead of adding a second one.
    caller_b.store(repo_root, *_components(), _payload("comp-b", 0.2), "2026-10-03T00:00:00Z")
    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 1

    monkeypatch.chdir(cwd_a)
    got_a = caller_a.fetch(repo_root, *_components())
    assert not isinstance(got_a, cache_manager.Miss)
    assert field(field(got_a, "payload"), "component_id") == "comp-b"
    assert field(got_a, "stored_at") == "2026-10-03T00:00:00Z"

    # A third "caller", the CLI, given the same four values, hits the same entry.
    capsys.readouterr()
    code = cache_manager.main(
        [
            "inspect",
            "--spec-bundle-hash=" + SPEC_BUNDLE_HASH,
            "--gate-inputs-hash",
            GATE_INPUTS_HASH,
            "--gate-version=" + GATE_VERSION,
            "--model-pin=" + MODEL_PIN,
            "--repo-root=" + str(repo_root),
        ]
    )
    assert code == 0
    out_lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(out_lines) == 1
    doc = json.loads(out_lines[0])
    assert doc["result"] == "hit"
    assert doc["gate_type"] == "license_scanner"
    assert doc["stored_at"] == "2026-10-03T00:00:00Z"


def test_each_component_is_part_of_the_key(tmp_path, monkeypatch):
    """Sanity guard: a store that collapsed every key into one entry would
    pass the test above. Changing any one of the four components must
    address a different entry."""
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    caller_a, caller_b = _load_callers(tmp_path)

    caller_a.store(repo_root, *_components(), _payload("comp-base", 0.0), "2026-10-02T00:00:00Z")
    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 1

    variants = [
        ("sha256:" + "c3" * 32, GATE_INPUTS_HASH, GATE_VERSION, MODEL_PIN),
        (SPEC_BUNDLE_HASH, "sha256:" + "d4" * 32, GATE_VERSION, MODEL_PIN),
        (SPEC_BUNDLE_HASH, GATE_INPUTS_HASH, "license_scanner@4.0.4+000000000000", MODEL_PIN),
        (SPEC_BUNDLE_HASH, GATE_INPUTS_HASH, GATE_VERSION, "claude-opus-5"),
    ]
    for index, variant in enumerate(variants):
        # Caller B misses on a variant before anyone has put it.
        assert isinstance(caller_b.fetch(repo_root, *variant), cache_manager.Miss)
        caller_b.store(repo_root, *variant, _payload("comp-v" + str(index), 0.0), "2026-10-02T00:00:00Z")
        assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == index + 2
        # Caller A, using the same variant components, hits B's entry.
        got = caller_a.fetch(repo_root, *variant)
        assert not isinstance(got, cache_manager.Miss)
        assert field(field(got, "payload"), "component_id") == "comp-v" + str(index)

    # The original entry still answers for the original components.
    base = caller_b.fetch(repo_root, *_components())
    assert not isinstance(base, cache_manager.Miss)
    assert field(field(base, "payload"), "component_id") == "comp-base"