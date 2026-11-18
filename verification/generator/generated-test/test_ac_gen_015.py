# hotdocs-criterion: sha256:789fc3eff19e25fdcb5d4c14bdc9a49abb4ea5dc65315862e5749161ec02c176
import re
from pathlib import Path

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_corpus(repo_root):
    _write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: false\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(comp / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def _fake_cache_manager_source(log_path, tag):
    return (
        "from __future__ import annotations\n"
        "\n"
        "import datetime\n"
        "from dataclasses import dataclass, field\n"
        "from typing import Any, ClassVar\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "TAG = " + repr(tag) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(TAG + ' ' + line + '\\n')\n"
        "\n"
        "\n"
        "_REQUIRED = {\n"
        "    'generator': ['component_id', 'model', 'prompt_version', 'files'],\n"
        "    'compiler': ['outputs', 'gate_version', 'summary'],\n"
        "    'generated_test': ['component_id', 'criterion_id', 'model', 'file'],\n"
        "    'llm_judge': ['result', 'rationale'],\n"
        "    'license_scanner': ['component_id', 'gate_version', 'similarity_score', 'blocked', 'matches'],\n"
        "    'secret_scanner': ['scope', 'gate_version', 'flagged', 'matches'],\n"
        "}\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str\n"
        "    gate_inputs_hash: str\n"
        "    gate_version: str\n"
        "    model_pin: str\n"
        "    _kind: ClassVar[str] = 'cache-key'\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class CachedResult:\n"
        "    gate_type: str\n"
        "    payload: dict[str, Any] = field(default_factory=dict)\n"
        "    stored_at: str = ''\n"
        "    _kind: ClassVar[str] = 'cached-result'\n"
        "\n"
        "\n"
        "class Miss:\n"
        "    def __eq__(self, other):\n"
        "        return isinstance(other, Miss)\n"
        "\n"
        "    def __hash__(self):\n"
        "        return hash('Miss')\n"
        "\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
        "\n"
        "\n"
        "_STORE = {}\n"
        "\n"
        "\n"
        "def _g(value, name):\n"
        "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
        "\n"
        "\n"
        "def _key_tuple(cache_key):\n"
        "    return (\n"
        "        _g(cache_key, 'spec_bundle_hash'),\n"
        "        _g(cache_key, 'gate_inputs_hash'),\n"
        "        _g(cache_key, 'gate_version'),\n"
        "        _g(cache_key, 'model_pin'),\n"
        "    )\n"
        "\n"
        "\n"
        "def now_iso():\n"
        "    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _log('get')\n"
        "    try:\n"
        "        hit = _STORE.get(_key_tuple(cache_key))\n"
        "    except Exception:\n"
        "        return Miss()\n"
        "    if hit is None:\n"
        "        return Miss()\n"
        "    return hit\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _log('put')\n"
        "    gate_version = _g(cache_key, 'gate_version')\n"
        "    gate_type = _g(result, 'gate_type')\n"
        "    if gate_type not in _REQUIRED or gate_version.split('@')[0] != gate_type:\n"
        "        raise SchemaValidationError('gate type mismatch')\n"
        "    payload = _g(result, 'payload')\n"
        "    for key in _REQUIRED[gate_type]:\n"
        "        if key not in payload:\n"
        "            raise SchemaValidationError('missing payload key: ' + key)\n"
        "    _STORE[_key_tuple(cache_key)] = result\n"
        "    return None\n"
        "\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return {'entry_count': len(_STORE)}\n"
        "\n"
        "\n"
        "def main(argv=None):\n"
        "    return 0\n"
        "\n"
        "\n"
        "_log('load')\n"
    )


def _make_repo(root, tag):
    root.mkdir(parents=True, exist_ok=True)
    _build_corpus(root)
    log_path = root.parent / (tag + "_cache_log.txt")
    _write(
        root / "gen" / "cache-manager" / "cache_manager.py",
        _fake_cache_manager_source(log_path, tag),
    )
    return log_path


def _make_bundle(hash_char):
    return {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + hash_char * 64,
        "spec": "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        "interface": "# Library\n\n```\nfoo(x: int) -> int\n```",
        "constraints": "# Constraints\n\nNone.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "# Glossary\n\n- **Foo** — a test term.",
        "hint_code": None,
    }


def _extract_nonce(prompt):
    m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})", prompt)
    if m:
        return m.group(1)
    m = re.search(r"\b([0-9a-f]{32})\b", prompt)
    assert m, "prompt does not state a nonce"
    return m.group(1)


def _make_backend(body):
    def backend(prompt, model, **params):
        nonce = _extract_nonce(prompt)
        text = (
            "Here is the file.\n"
            + "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            + body
            + "-----END FILE " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def _read_lines(path):
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _assert_success(result):
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    files = field(result, "files")
    assert files, "expected non-empty files"


def test_ac_gen_015_per_call_dynamic_cache_manager_loading(tmp_path):
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    log_a = _make_repo(repo_a, "A")
    log_b = _make_repo(repo_b, "B")

    body_a = "def foo(x):\n    return 2 * x\n"
    body_b = "def foo(x):\n    return x + x\n"

    # First call, against repo_a: must not raise (dataclasses resolve cleanly).
    result_a = generator.generate(
        _make_bundle("a"),
        "mock-model",
        None,
        repo_root=repo_a,
        llm_backend=_make_backend(body_a),
    )
    _assert_success(result_a)

    lines_a_after_first = _read_lines(log_a)
    lines_b_after_first = _read_lines(log_b)
    assert any(
        line.split(" ", 1)[1] in ("get", "put") for line in lines_a_after_first
    ), "first call did not use repo_a's cache-manager: " + repr(lines_a_after_first)
    assert all(line.startswith("A ") for line in lines_a_after_first)
    assert lines_b_after_first == [], "first call touched repo_b's cache-manager"

    # Second call, same process, against repo_b: must not raise either.
    result_b = generator.generate(
        _make_bundle("b"),
        "mock-model",
        None,
        repo_root=repo_b,
        llm_backend=_make_backend(body_b),
    )
    _assert_success(result_b)

    lines_a_after_second = _read_lines(log_a)
    lines_b_after_second = _read_lines(log_b)

    # The second call must use repo_b's own cache-manager...
    assert any(
        line.split(" ", 1)[1] in ("get", "put") for line in lines_b_after_second
    ), "second call did not use repo_b's cache-manager: " + repr(lines_b_after_second)
    assert all(line.startswith("B ") for line in lines_b_after_second)

    # ...and not the first call's (stale) repo_a module.
    assert lines_a_after_second == lines_a_after_first, (
        "second call reused repo_a's cache-manager: "
        + repr(lines_a_after_second[len(lines_a_after_first):])
    )