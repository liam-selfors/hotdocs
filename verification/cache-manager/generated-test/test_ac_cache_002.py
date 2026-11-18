# hotdocs-criterion: sha256:94d46df8610db6edbb8312679ddd5f626fb4262ba7128ca6b80701b52008d07d
"""AC-CACHE-002 (covers R-CACHE-002).

Given the same four key components (spec_bundle_hash, gate_inputs_hash,
gate_version, model_pin) supplied by two different calling components,
when each computes the cache key for a put, then both produce
byte-identical serialized keys.

The interface exposes no serialized-key accessor, so the test checks
identical key formation through behavior. Two independent caller modules
are loaded from separate files. Each builds its own CacheKey from the same
four components, using different construction styles. The test then checks:

* A hit written by one caller is visible to the other caller, and to the CLI.
* A put by the second caller under "the same" key lands in the same slot.
  The store's entry_count does not grow, and the first caller then sees
  the second caller's payload, which is last-write-wins on one key.
* Changing any single one of the four components produces a different key
  (a miss, and a new entry). This rules out a trivially constant key.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

import cache_manager


SPEC_BUNDLE_HASH = "sha256:" + "ab" * 32
GATE_INPUTS_HASH = "sha256:" + "cd" * 32
GATE_VERSION = "license_scanner@4.0.3+9f2c41ab07de"
MODEL_PIN = "claude-sonnet-5"


CALLER_ALPHA_SRC = '''
import cache_manager

CALLER_ID = "comp-alpha-caller"


def make_key(spec_bundle_hash, gate_inputs_hash, gate_version, model_pin):
    return cache_manager.CacheKey(
        spec_bundle_hash=spec_bundle_hash,
        gate_inputs_hash=gate_inputs_hash,
        gate_version=gate_version,
        model_pin=model_pin,
    )


def do_put(components, payload, repo_root):
    key = make_key(
        components["spec_bundle_hash"],
        components["gate_inputs_hash"],
        components["gate_version"],
        components["model_pin"],
    )
    gate_type = components["gate_version"].split("@", 1)[0]
    result = cache_manager.CachedResult(
        gate_type=gate_type,
        payload=payload,
        stored_at=cache_manager.now_iso(),
    )
    cache_manager.put(key, result, repo_root=repo_root)


def do_get(components, repo_root):
    key = make_key(
        components["spec_bundle_hash"],
        components["gate_inputs_hash"],
        components["gate_version"],
        components["model_pin"],
    )
    return cache_manager.get(key, repo_root=repo_root)
'''


CALLER_BETA_SRC = '''
from pathlib import Path

import cache_manager

CALLER_ID = "comp-beta-caller"


def _fresh(s):
    # Rebuild the string character by character so it is a distinct,
    # non-interned object with equal content.
    return "".join(list(str(s)))


def make_key(components):
    # Keywords deliberately supplied in reverse order.
    return cache_manager.CacheKey(
        model_pin=_fresh(components["model_pin"]),
        gate_version=_fresh(components["gate_version"]),
        gate_inputs_hash=_fresh(components["gate_inputs_hash"]),
        spec_bundle_hash=_fresh(components["spec_bundle_hash"]),
    )


def do_put(components, payload, repo_root):
    key = make_key(components)
    gate_type = _fresh(components["gate_version"]).partition("@")[0]
    result = cache_manager.CachedResult(
        stored_at=cache_manager.now_iso(),
        payload=payload,
        gate_type=gate_type,
    )
    cache_manager.put(key, result, repo_root=Path(str(repo_root)))


def do_get(components, repo_root):
    return cache_manager.get(make_key(components), repo_root=Path(str(repo_root)))
'''


def _load_module(module_name, module_path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # register BEFORE exec_module
    spec.loader.exec_module(module)
    return module


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _entry_count(repo_root):
    s = cache_manager.stats(repo_root=repo_root)
    return _field(s, "entry_count")


def _components(**overrides):
    base = {
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "gate_inputs_hash": GATE_INPUTS_HASH,
        "gate_version": GATE_VERSION,
        "model_pin": MODEL_PIN,
    }
    base.update(overrides)
    return base


def _payload(marker, gate_version=GATE_VERSION):
    return {
        "component_id": "comp-widget",
        "gate_version": gate_version,
        "similarity_score": 0.0 if marker == "alpha" else 0.01,
        "blocked": False,
        "matches": [],
        "marker": marker,
    }


def _is_hit(result):
    return result is not None and not isinstance(result, cache_manager.Miss)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    callers_dir = tmp_path / "callers"
    callers_dir.mkdir()
    alpha_path = callers_dir / "ac_cache_002_caller_alpha.py"
    beta_path = callers_dir / "ac_cache_002_caller_beta.py"
    alpha_path.write_text(CALLER_ALPHA_SRC, encoding="utf-8")
    beta_path.write_text(CALLER_BETA_SRC, encoding="utf-8")

    alpha = _load_module("ac_cache_002_caller_alpha", alpha_path)
    beta = _load_module("ac_cache_002_caller_beta", beta_path)
    try:
        yield repo_root, alpha, beta
    finally:
        sys.modules.pop("ac_cache_002_caller_alpha", None)
        sys.modules.pop("ac_cache_002_caller_beta", None)


def _run_cli(argv, capsys):
    capsys.readouterr()
    code = cache_manager.main(argv)
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert lines, "CLI produced no output"
    return code, json.loads(lines[-1])


def test_two_callers_form_identical_keys_for_same_components(env, capsys):
    repo_root, alpha, beta = env
    comps = _components()

    assert _entry_count(repo_root) == 0

    # Caller alpha puts under its own independently formed key.
    alpha.do_put(dict(comps), _payload("alpha"), repo_root)
    assert _entry_count(repo_root) == 1

    # Caller beta, forming its own key from the same components, must hit.
    got_by_beta = beta.do_get(dict(comps), repo_root)
    assert _is_hit(got_by_beta), "beta's key did not match alpha's stored key"
    assert _field(got_by_beta, "gate_type") == "license_scanner"
    beta_payload = _field(got_by_beta, "payload")
    assert _field(beta_payload, "marker") == "alpha"

    # Alpha also sees its own write.
    got_by_alpha = alpha.do_get(dict(comps), repo_root)
    assert _is_hit(got_by_alpha)

    # The CLI is a third caller. It forms the key from flags and must hit too.
    code, out = _run_cli(
        [
            "inspect",
            f"--spec-bundle-hash={SPEC_BUNDLE_HASH}",
            f"--gate-inputs-hash={GATE_INPUTS_HASH}",
            f"--gate-version={GATE_VERSION}",
            f"--model-pin={MODEL_PIN}",
            f"--repo-root={repo_root}",
        ],
        capsys,
    )
    assert code == 0
    assert out.get("result") == "hit"
    assert out.get("gate_type") == "license_scanner"
    assert "payload" not in out

    # Beta puts under "the same" key. It must land in the same slot, so the
    # entry count does not grow.
    beta.do_put(dict(comps), _payload("beta"), repo_root)
    assert _entry_count(repo_root) == 1, (
        "beta's put created a separate entry; its serialized key differs "
        "from alpha's"
    )

    # Last write wins on the single shared key: alpha now reads beta's payload.
    got_after = alpha.do_get(dict(comps), repo_root)
    assert _is_hit(got_after)
    assert _field(_field(got_after, "payload"), "marker") == "beta"


@pytest.mark.parametrize(
    "field,alt_value",
    [
        ("spec_bundle_hash", "sha256:" + "ef" * 32),
        ("gate_inputs_hash", "sha256:" + "01" * 32),
        ("gate_version", "license_scanner@4.0.4+0000000000aa"),
        ("model_pin", "claude-opus-5"),
    ],
)
def test_each_component_participates_in_key(env, field, alt_value):
    repo_root, alpha, beta = env
    comps = _components()

    alpha.do_put(dict(comps), _payload("alpha"), repo_root)
    assert _entry_count(repo_root) == 1

    varied = _components(**{field: alt_value})

    # A key that differs in exactly one component is a different key for
    # both callers.
    assert isinstance(beta.do_get(dict(varied), repo_root), cache_manager.Miss)
    assert isinstance(alpha.do_get(dict(varied), repo_root), cache_manager.Miss)

    beta.do_put(
        dict(varied),
        _payload("beta", gate_version=varied["gate_version"]),
        repo_root,
    )
    assert _entry_count(repo_root) == 2

    # Both keys stay independently retrievable by either caller.
    orig = beta.do_get(dict(comps), repo_root)
    assert _is_hit(orig)
    assert _field(_field(orig, "payload"), "marker") == "alpha"

    alt = alpha.do_get(dict(varied), repo_root)
    assert _is_hit(alt)
    assert _field(_field(alt, "payload"), "marker") == "beta"