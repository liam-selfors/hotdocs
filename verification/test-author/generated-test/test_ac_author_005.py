import json
import re

import test_author


EXPECTED = "import foo\n\n\ndef test_foo_doubles():\n    assert foo.foo(2) == 4"
MODEL = "claude-sonnet-5"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


class Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle():
    return Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text=(
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4"
        ),
        requirement_text="**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


def write_fake_cache_manager(repo_root, store_path, log_path):
    lines = [
        "import json",
        "import os",
        "from dataclasses import dataclass, field as _dc_field",
        "from datetime import datetime, timezone",
        "",
        "_STORE = " + repr(str(store_path)),
        "_LOG = " + repr(str(log_path)),
        "",
        "_REQUIRED = {",
        "    'generator': ['component_id', 'model', 'prompt_version', 'files'],",
        "    'compiler': ['outputs', 'gate_version', 'summary'],",
        "    'generated_test': ['component_id', 'criterion_id', 'model', 'file'],",
        "    'llm_judge': ['result', 'rationale'],",
        "    'license_scanner': ['component_id', 'gate_version', 'similarity_score', 'blocked', 'matches'],",
        "    'secret_scanner': ['scope', 'gate_version', 'flagged', 'matches'],",
        "}",
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
        "def _f(value, name):",
        "    return value[name] if isinstance(value, dict) else getattr(value, name)",
        "",
        "",
        "def _plain(value):",
        "    return json.loads(json.dumps(value, default=lambda o: getattr(o, '__dict__', str(o))))",
        "",
        "",
        "def _key_dict(cache_key):",
        "    return {",
        "        'spec_bundle_hash': _f(cache_key, 'spec_bundle_hash'),",
        "        'gate_inputs_hash': _f(cache_key, 'gate_inputs_hash'),",
        "        'gate_version': _f(cache_key, 'gate_version'),",
        "        'model_pin': _f(cache_key, 'model_pin'),",
        "    }",
        "",
        "",
        "def _load():",
        "    if not os.path.exists(_STORE):",
        "        return []",
        "    with open(_STORE, 'r', encoding='utf-8') as fh:",
        "        return json.load(fh)",
        "",
        "",
        "def _log(line):",
        "    with open(_LOG, 'a', encoding='utf-8') as fh:",
        "        fh.write(line + '\\n')",
        "",
        "",
        "def now_iso():",
        "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')",
        "",
        "",
        "def get(cache_key, *, repo_root=None):",
        "    _log('get')",
        "    try:",
        "        key = _plain(_key_dict(cache_key))",
        "        for entry in _load():",
        "            if entry['key'] == key:",
        "                r = entry['result']",
        "                return CachedResult(gate_type=r['gate_type'], payload=r['payload'], stored_at=r['stored_at'])",
        "    except Exception:",
        "        return Miss()",
        "    return Miss()",
        "",
        "",
        "def put(cache_key, result, *, repo_root=None):",
        "    _log('put')",
        "    key = _plain(_key_dict(cache_key))",
        "    gate_type = _f(result, 'gate_type')",
        "    payload = _plain(_f(result, 'payload'))",
        "    stored_at = _f(result, 'stored_at')",
        "    if gate_type not in _REQUIRED:",
        "        raise SchemaValidationError('unknown gate_type')",
        "    if key['gate_version'].split('@', 1)[0] != gate_type:",
        "        raise SchemaValidationError('gate_type does not match gate_version')",
        "    if not isinstance(payload, dict):",
        "        raise SchemaValidationError('payload must be a mapping')",
        "    for k in _REQUIRED[gate_type]:",
        "        if k not in payload:",
        "            raise SchemaValidationError('missing payload key ' + k)",
        "    entries = [e for e in _load() if e['key'] != key]",
        "    entries.append({'key': key, 'result': {'gate_type': gate_type, 'payload': payload, 'stored_at': stored_at}})",
        "    tmp = _STORE + '.tmp'",
        "    with open(tmp, 'w', encoding='utf-8') as fh:",
        "        json.dump(entries, fh)",
        "    os.replace(tmp, _STORE)",
        "",
        "",
        "def stats(*, repo_root=None):",
        "    return {'entry_count': len(_load())}",
        "",
    ]
    target_dir = repo_root / "gen" / "cache-manager"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "cache_manager.py").write_text("\n".join(lines), encoding="utf-8")


def make_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        match = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        assert match is not None, "prompt carries no nonce"
        n = match.group(1)
        text = "-----BEGIN FILE " + n + "-----\n" + EXPECTED + "\n-----END FILE " + n + "-----"
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def read_lines(path):
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]


def file_content(file_value):
    if isinstance(file_value, str):
        return file_value
    return field(file_value, "content")


def test_cache_miss_result_is_written_to_cache_under_correct_key(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    store_path = tmp_path / "cache_store.json"
    cache_log = tmp_path / "cache_calls.log"
    backend_log = tmp_path / "backend_calls.log"

    write_fake_cache_manager(repo_root, store_path, cache_log)

    # Given an empty cache
    assert not store_path.exists()

    bundle = make_bundle()
    backend = make_backend(backend_log)

    # When author_test is called
    result = test_author.author_test(bundle, MODEL, 0, repo_root=repo_root, llm_backend=backend)

    assert field(result, "model_call_error") is None
    assert field(result, "cache_hit") is False
    assert len(read_lines(backend_log)) == 1
    assert body(file_content(field(result, "file"))) == EXPECTED

    # Then cache-manager contains that result
    assert "put" in read_lines(cache_log), "author_test never wrote to cache-manager"
    assert store_path.exists()
    entries = json.loads(store_path.read_text(encoding="utf-8"))
    assert len(entries) == 1
    entry = entries[0]
    key = entry["key"]
    stored = entry["result"]

    assert stored["gate_type"] == "generated_test"
    payload = stored["payload"]
    assert payload["component_id"] == "comp-foo"
    assert payload["criterion_id"] == "AC-FOO-001"
    assert payload["model"] == MODEL
    assert body(file_content(payload["file"])) == EXPECTED

    # ... under the correct key
    assert key["gate_version"].split("@", 1)[0] == "generated_test"
    assert key["model_pin"] == MODEL

    # The key written is the one author_test itself looks up: a repeat call is
    # served from the cache without calling the model again.
    second = test_author.author_test(bundle, MODEL, 0, repo_root=repo_root, llm_backend=backend)
    assert field(second, "model_call_error") is None
    assert field(second, "cache_hit") is True
    assert len(read_lines(backend_log)) == 1
    assert body(file_content(field(second, "file"))) == EXPECTED