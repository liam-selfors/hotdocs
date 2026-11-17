# hotdocs-criterion: sha256:37950c581c396e8eb020aa7396c13710faaf3ad7eac564138e61d4c95f973025
import hashlib
import json
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclass
class FakeSpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dc_field(default_factory=dict)
    dependency_context: dict = dc_field(default_factory=dict)
    dependency_usage: dict = dc_field(default_factory=dict)
    vars: dict = dc_field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def _names(self):
        return [
            "component_id", "spec_bundle_hash", "spec", "interface",
            "constraints", "dependency_interfaces", "dependency_context",
            "dependency_usage", "vars", "glossary", "hint_code",
        ]

    def __getitem__(self, key):
        if key not in self._names():
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self._names():
            return getattr(self, key)
        return default

    def keys(self):
        return list(self._names())

    def __iter__(self):
        return iter(self._names())

    def __contains__(self, key):
        return key in self._names()

    def __len__(self):
        return len(self._names())


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(repo_root):
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a test term.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "component.md",
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
        repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "acceptance" / "AC-FOO-001.md",
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
    _write(
        repo_root / "specs" / "components" / "foo" / "interface" / "library.md",
        "# Library\n\n```\nfoo(x: int) -> int\n```\n",
    )
    _write(
        repo_root / "specs" / "components" / "foo" / "constraints.md",
        "# Constraints\n\nNone.\n",
    )


def _write_fake_cache_manager(repo_root, expected_key, cached_payload, log_path):
    src = (
        "import datetime\n"
        "from dataclasses import dataclass\n"
        "\n"
        "EXPECTED_KEY = " + repr(expected_key) + "\n"
        "CACHED_PAYLOAD = " + repr(cached_payload) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "def _field(value, name):\n"
        "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
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
        "    payload: dict\n"
        "    stored_at: str\n"
        "\n"
        "\n"
        "class Miss:\n"
        "    def __eq__(self, other):\n"
        "        return isinstance(other, Miss)\n"
        "\n"
        "    def __hash__(self):\n"
        "        return hash('Miss')\n"
        "\n"
        "    def __repr__(self):\n"
        "        return 'Miss()'\n"
        "\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
        "\n"
        "\n"
        "def now_iso():\n"
        "    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    try:\n"
        "        actual = {name: _field(cache_key, name) for name in EXPECTED_KEY}\n"
        "    except Exception:\n"
        "        _log('get-miss')\n"
        "        return Miss()\n"
        "    if actual == EXPECTED_KEY:\n"
        "        _log('get-hit')\n"
        "        return CachedResult(\n"
        "            gate_type='generator',\n"
        "            payload=dict(CACHED_PAYLOAD),\n"
        "            stored_at='2026-01-01T00:00:00Z',\n"
        "        )\n"
        "    _log('get-miss')\n"
        "    return Miss()\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _log('put')\n"
        "    return None\n"
        "\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return {'entry_count': 0}\n"
    )
    _write(repo_root / "gen" / "cache-manager" / "cache_manager.py", src)


def _read_log(path):
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.parametrize("retry_feedback", [None, ["R-FOO-001"]])
def test_cache_hit_returns_cached_result_without_model_call(tmp_path, retry_feedback):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    model = "claude-sonnet-5"
    spec_bundle_hash = "sha256:" + hashlib.sha256(b"comp-foo-bundle").hexdigest()
    gate_inputs_hash = "sha256:" + hashlib.sha256(
        json.dumps(sorted(retry_feedback or []), sort_keys=True).encode("utf-8")
    ).hexdigest()

    expected_key = {
        "spec_bundle_hash": spec_bundle_hash,
        "gate_inputs_hash": gate_inputs_hash,
        "gate_version": generator.GATE_VERSION,
        "model_pin": model,
    }

    cached_files = {"foo.py": "def foo(x):\n    # served from cache\n    return 2 * x\n"}
    cached_payload = {
        "component_id": "comp-foo",
        "spec_bundle_hash": spec_bundle_hash,
        "model": model,
        "prompt_version": generator.PROMPT_VERSION,
        "cache_hit": False,
        "files": cached_files,
        "model_call_error": None,
        "refused": None,
        "retry_feedback": list(retry_feedback) if retry_feedback else None,
    }

    cache_log = tmp_path / "cache_calls.log"
    model_log = tmp_path / "model_calls.log"
    _write_fake_cache_manager(repo_root, expected_key, cached_payload, cache_log)

    def mock_backend(prompt, model, **params):
        with open(model_log, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        return {
            "text": "no files here",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = FakeSpecBundle(
        component_id="comp-foo",
        spec_bundle_hash=spec_bundle_hash,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
    )

    result = generator.generate(
        bundle,
        model,
        retry_feedback,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    # The fake cache-manager was actually consulted and reported a hit.
    cache_lines = _read_log(cache_log)
    assert "get-hit" in cache_lines, cache_lines

    # The mock model was never called.
    assert _read_log(model_log) == []

    # The cached result is what was returned.
    assert field(result, "files") == cached_files
    assert field(result, "cache_hit") is True
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "component_id") == "comp-foo"
    assert field(result, "spec_bundle_hash") == spec_bundle_hash