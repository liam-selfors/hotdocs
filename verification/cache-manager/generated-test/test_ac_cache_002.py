# hotdocs-criterion: sha256:c4ef25dbf6ccb560209afe6abaebde1202e4d93c161f93c7113fbd80e6560e79
"""AC-CACHE-002 (covers R-CACHE-002).

Given the same four key components (spec_bundle_hash, gate_inputs_hash,
gate_version, model_pin) supplied by two different calling components,
when each computes the cache key for a put, then both produce
byte-identical serialized keys.

The serialized key is internal to cache_manager, so the test observes it
through the public interface. Two independent caller modules each build
the key their own way and put under it. Byte-identical keys mean:
- the local store holds exactly one entry afterwards (stats),
- each caller's get finds what the other caller wrote,
- the CLI's inspect, a third independent route, also hits.
A control key that differs in one component misses, so a hit is not
returned for every key.
"""

import importlib.util
import json
import sys
from pathlib import Path

import cache_manager


SPEC_BUNDLE_HASH = "sha256:" + "a1" * 32
GATE_INPUTS_HASH = "sha256:" + "b2" * 32
GATE_VERSION = "license_scanner@4.0.3+9f2c41ab07de"
MODEL_PIN = "claude-sonnet-5"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Caller A builds the key with keyword arguments in the documented field
# order, from the strings it was handed.
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
    "def do_put(repo_root, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):\n"
    "    key = make_key(spec_bundle_hash, gate_inputs_hash, gate_version, model_pin)\n"
    "    result = cache_manager.CachedResult(\n"
    "        gate_type='license_scanner',\n"
    "        payload=dict(\n"
    "            component_id='comp-caller-a',\n"
    "            gate_version=gate_version,\n"
    "            similarity_score=0.0,\n"
    "            blocked=False,\n"
    "            matches=[],\n"
    "        ),\n"
    "        stored_at=cache_manager.now_iso(),\n"
    "    )\n"
    "    cache_manager.put(key, result, repo_root=repo_root)\n"
    "\n"
    "def do_get(repo_root, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):\n"
    "    key = make_key(spec_bundle_hash, gate_inputs_hash, gate_version, model_pin)\n"
    "    return cache_manager.get(key, repo_root=repo_root)\n"
)

# Caller B builds the key differently: keyword arguments in reverse order,
# from freshly rebuilt (non-identical) string objects.
CALLER_B_SOURCE = (
    "import cache_manager\n"
    "\n"
    "def _fresh(s):\n"
    "    return ''.join(list(s))\n"
    "\n"
    "def make_key(spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):\n"
    "    return cache_manager.CacheKey(\n"
    "        model_pin=_fresh(model_pin),\n"
    "        gate_version=_fresh(gate_version),\n"
    "        gate_inputs_hash=_fresh(gate_inputs_hash),\n"
    "        spec_bundle_hash=_fresh(spec_bundle_hash),\n"
    "    )\n"
    "\n"
    "def do_put(repo_root, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):\n"
    "    key = make_key(spec_bundle_hash, gate_inputs_hash, gate_version, model_pin)\n"
    "    result = cache_manager.CachedResult(\n"
    "        gate_type='license_scanner',\n"
    "        payload=dict(\n"
    "            component_id='comp-caller-b',\n"
    "            gate_version=gate_version,\n"
    "            similarity_score=0.0,\n"
    "            blocked=False,\n"
    "            matches=[],\n"
    "        ),\n"
    "        stored_at=cache_manager.now_iso(),\n"
    "    )\n"
    "    cache_manager.put(key, result, repo_root=repo_root)\n"
    "\n"
    "def do_get(repo_root, spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):\n"
    "    key = make_key(spec_bundle_hash, gate_inputs_hash, gate_version, model_pin)\n"
    "    return cache_manager.get(key, repo_root=repo_root)\n"
)


def _write_callers(tmp_path):
    callers_dir = tmp_path / "callers"
    callers_dir.mkdir()
    a_path = callers_dir / "ac_cache_002_caller_a.py"
    b_path = callers_dir / "ac_cache_002_caller_b.py"
    a_path.write_text(CALLER_A_SOURCE, encoding="utf-8")
    b_path.write_text(CALLER_B_SOURCE, encoding="utf-8")
    caller_a = load_module(a_path, "ac_cache_002_caller_a")
    caller_b = load_module(b_path, "ac_cache_002_caller_b")
    return caller_a, caller_b


def _components():
    return (SPEC_BUNDLE_HASH, GATE_INPUTS_HASH, GATE_VERSION, MODEL_PIN)


def _setup(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    return repo_root


def _cli_inspect(repo_root, capsys, model_pin=MODEL_PIN):
    capsys.readouterr()
    code = cache_manager.main(
        [
            "inspect",
            "--spec-bundle-hash=" + SPEC_BUNDLE_HASH,
            "--gate-inputs-hash=" + GATE_INPUTS_HASH,
            "--gate-version=" + GATE_VERSION,
            "--model-pin=" + model_pin,
            "--repo-root=" + str(repo_root),
        ]
    )
    out = capsys.readouterr().out
    lines = [line for line in out.splitlines() if line.strip()]
    assert code == 0, out
    assert lines, "inspect printed nothing on stdout"
    return json.loads(lines[-1])


def test_two_callers_putting_same_components_produce_one_identical_key(
    tmp_path, monkeypatch, capsys
):
    repo_root = _setup(tmp_path, monkeypatch)
    caller_a, caller_b = _write_callers(tmp_path)

    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 0

    caller_a.do_put(repo_root, *_components())
    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 1

    caller_b.do_put(repo_root, *_components())
    # Identical serialized keys: B's put lands on A's entry (last write
    # wins) rather than creating a second, differently-keyed entry.
    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 1

    # Each caller's key finds the single stored entry.
    for caller in (caller_a, caller_b):
        got = caller.do_get(repo_root, *_components())
        assert not isinstance(got, cache_manager.Miss)
        assert field(got, "gate_type") == "license_scanner"
        payload = field(got, "payload")
        # Last write wins: caller B wrote last.
        assert field(payload, "component_id") == "comp-caller-b"

    # A third independent route (the CLI) forms the same key too.
    inspected = _cli_inspect(repo_root, capsys)
    assert inspected["result"] == "hit"
    assert inspected["gate_type"] == "license_scanner"


def test_key_written_by_one_caller_is_found_by_the_other(tmp_path, monkeypatch, capsys):
    repo_root = _setup(tmp_path, monkeypatch)
    caller_a, caller_b = _write_callers(tmp_path)

    # Before any put, every route misses.
    assert isinstance(caller_a.do_get(repo_root, *_components()), cache_manager.Miss)
    assert isinstance(caller_b.do_get(repo_root, *_components()), cache_manager.Miss)

    caller_a.do_put(repo_root, *_components())

    got_by_b = caller_b.do_get(repo_root, *_components())
    assert not isinstance(got_by_b, cache_manager.Miss)
    assert field(got_by_b, "gate_type") == "license_scanner"
    assert field(field(got_by_b, "payload"), "component_id") == "comp-caller-a"

    inspected = _cli_inspect(repo_root, capsys)
    assert inspected["result"] == "hit"

    # Control: a key differing in one component is a different key.
    other = caller_b.do_get(
        repo_root, SPEC_BUNDLE_HASH, GATE_INPUTS_HASH, GATE_VERSION, "claude-opus-5"
    )
    assert isinstance(other, cache_manager.Miss)
    assert _cli_inspect(repo_root, capsys, model_pin="claude-opus-5") == {"result": "miss"}
    assert field(cache_manager.stats(repo_root=repo_root), "entry_count") == 1