# hotdocs-criterion: sha256:789fc3eff19e25fdcb5d4c14bdc9a49abb4ea5dc65315862e5749161ec02c176
"""AC-GEN-015 (R-GEN-014): per-call dependency loading from two different
repo_roots in one process must resolve each repo_root's own cache-manager,
whose dataclasses must evaluate cleanly both times."""

import re
from pathlib import Path

import generator


NONCE_RE = r"-----BEGIN FILE ([0-9a-f]{32}):"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _fake_cache_manager_source(tag, log_path):
    return (
        "from __future__ import annotations\n"
        "\n"
        "import time\n"
        "from dataclasses import dataclass, field\n"
        "from typing import Any\n"
        "\n"
        "TAG = " + repr(tag) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "KNOWN_GATE_TYPES = {\n"
        "    'generator': ['component_id', 'model', 'prompt_version', 'files'],\n"
        "    'compiler': ['outputs', 'gate_version', 'summary'],\n"
        "    'generated_test': ['component_id', 'criterion_id', 'model', 'file'],\n"
        "    'llm_judge': ['result', 'rationale'],\n"
        "    'license_scanner': ['component_id', 'gate_version', 'similarity_score', 'blocked', 'matches'],\n"
        "    'secret_scanner': ['scope', 'gate_version', 'flagged', 'matches'],\n"
        "}\n"
        "\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str\n"
        "    gate_inputs_hash: str\n"
        "    gate_version: str\n"
        "    model_pin: str\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class CachedResult:\n"
        "    gate_type: str\n"
        "    payload: dict[str, Any] = field(default_factory=dict)\n"
        "    stored_at: str = ''\n"
        "\n"
        "\n"
        "class Miss:\n"
        "    def __eq__(self, other):\n"
        "        return isinstance(other, Miss)\n"
        "\n"
        "    def __hash__(self):\n"
        "        return 0\n"
        "\n"
        "    def __repr__(self):\n"
        "        return 'Miss()'\n"
        "\n"
        "\n"
        "_STORE = {}\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "def _f(value, name):\n"
        "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
        "\n"
        "\n"
        "def _key(cache_key):\n"
        "    return (\n"
        "        _f(cache_key, 'spec_bundle_hash'),\n"
        "        _f(cache_key, 'gate_inputs_hash'),\n"
        "        _f(cache_key, 'gate_version'),\n"
        "        _f(cache_key, 'model_pin'),\n"
        "    )\n"
        "\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _log('get ' + TAG + ' ' + str(isinstance(cache_key, CacheKey)))\n"
        "    return Miss()\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    gate_type = _f(result, 'gate_type')\n"
        "    expected = str(_f(cache_key, 'gate_version')).split('@', 1)[0]\n"
        "    if gate_type not in KNOWN_GATE_TYPES or gate_type != expected:\n"
        "        raise SchemaValidationError('bad gate_type')\n"
        "    payload = _f(result, 'payload')\n"
        "    for k in KNOWN_GATE_TYPES[gate_type]:\n"
        "        if k not in payload:\n"
        "            raise SchemaValidationError('missing ' + k)\n"
        "    _log('put ' + TAG)\n"
        "    _STORE[_key(cache_key)] = result\n"
        "\n"
        "\n"
        "def now_iso():\n"
        "    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())\n"
        "\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return {'entry_count': len(_STORE)}\n"
        "\n"
        "\n"
        "def main(argv=None):\n"
        "    return 0\n"
    )


def _make_repo(root, tag, log_path):
    root.mkdir(parents=True, exist_ok=True)
    cm_dir = root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True, exist_ok=True)
    (cm_dir / "cache_manager.py").write_text(
        _fake_cache_manager_source(tag, log_path), encoding="utf-8"
    )
    return root


def _bundle(hash_suffix):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + hash_suffix * 64,
        "spec": "# Foo\n\nFoo doubles a number.\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        "interface": "# Library\n\n```\nfoo(x: int) -> int\n```",
        "constraints": "None.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "- **Foo** — a test term.",
        "hint_code": None,
    }


def _mock_backend(prompt, model, **params):
    nonce = re.search(NONCE_RE, prompt).group(1)
    text = (
        "-----BEGIN FILE " + nonce + ": foo.py-----\n"
        "def foo(x):\n"
        "    return 2 * x\n"
        "-----END FILE " + nonce + "-----\n"
        "-----END REPLY " + nonce + "-----\n"
    )
    return {
        "text": text,
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def _read_log(log_path):
    if not log_path.exists():
        return []
    return [ln for ln in log_path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _assert_success(result):
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False
    files = field(result, "files")
    assert files, "expected a non-empty files mapping"


def test_two_repo_roots_each_resolve_their_own_cache_manager(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    log_path = tmp_path / "cache_manager_calls.log"
    repo_a = _make_repo(tmp_path / "repo_a", "A", log_path)
    repo_b = _make_repo(tmp_path / "repo_b", "B", log_path)

    # First call: repo A.
    result_a = generator.generate(
        _bundle("a"), "mock-model", None, repo_root=repo_a, llm_backend=_mock_backend
    )
    _assert_success(result_a)

    lines_after_a = _read_log(log_path)
    get_lines_a = [ln for ln in lines_after_a if ln.startswith("get ")]
    assert get_lines_a, "repo A's cache-manager get was never called"
    assert all(ln.split()[1] == "A" for ln in get_lines_a), lines_after_a
    # The CacheKey handed to get was built from repo A's own CacheKey dataclass.
    assert all(ln.split()[2] == "True" for ln in get_lines_a), lines_after_a

    # Second call, same process: repo B, with its own cache-manager.
    result_b = generator.generate(
        _bundle("b"), "mock-model", None, repo_root=repo_b, llm_backend=_mock_backend
    )
    _assert_success(result_b)

    new_lines = _read_log(log_path)[len(lines_after_a):]
    get_lines_b = [ln for ln in new_lines if ln.startswith("get ")]
    assert get_lines_b, "repo B's cache-manager get was never called (stale module reused?)"
    assert all(ln.split()[1] == "B" for ln in get_lines_b), (
        "second call used repo A's cache-manager instead of repo B's: " + repr(new_lines)
    )
    assert all(ln.split()[2] == "True" for ln in get_lines_b), new_lines