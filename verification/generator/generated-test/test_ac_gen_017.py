# hotdocs-criterion: sha256:c36b3ea5268e4ed334707889d2c530193fc1c902b209e06913a47e0671b17843
import json
import re
from pathlib import Path

import pytest

import generator


MODEL = "mock-model"
COMPONENT_ID = "comp-foo"
SLUG = "foo"
SPEC_BUNDLE_HASH = "sha256:" + "ab" * 32
EXISTING_FOO = "def foo(x):\n    return x + x\n"
MOCK_FOO = "def foo(x):\n    return 2 * x\n"
CACHED_FOO = "def foo(x):\n    return x * 2  # cached\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle:
    """An object carrying the SpecBundle fields, readable both by attribute and as a mapping."""

    _FIELDS = (
        "component_id",
        "spec_bundle_hash",
        "spec",
        "interface",
        "constraints",
        "dependency_interfaces",
        "dependency_context",
        "dependency_usage",
        "vars",
        "glossary",
        "hint_code",
    )

    def __init__(self, **kwargs):
        for name in self._FIELDS:
            setattr(self, name, kwargs.get(name))

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key not in self._FIELDS:
            return default
        return getattr(self, key)

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def __contains__(self, key):
        return key in self._FIELDS


def make_bundle():
    return Bundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash=SPEC_BUNDLE_HASH,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
        hint_code={"foo.py": EXISTING_FOO},
    )


def write_component(repo_root):
    comp_dir = repo_root / "specs" / "components" / SLUG
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
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
        encoding="utf-8",
    )
    gen_dir = repo_root / "gen" / SLUG
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "foo.py").write_text(EXISTING_FOO, encoding="utf-8")


def snapshot(directory):
    result = {}
    directory = Path(directory)
    if not directory.exists():
        return None
    for p in sorted(directory.rglob("*")):
        rel = p.relative_to(directory).as_posix()
        if p.is_file():
            result[rel] = p.read_bytes()
        else:
            result[rel] = None
    return result


def write_fake_cache_manager(repo_root, log_path, hit_hash, hit_payload):
    source = (
        "import dataclasses\n"
        "import datetime\n"
        "import json\n"
        "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "HIT_HASH = " + repr(hit_hash) + "\n"
        "HIT_PAYLOAD = " + repr(hit_payload) + "\n"
        "\n"
        "\n"
        "@dataclasses.dataclass\n"
        "class CacheKey:\n"
        "    spec_bundle_hash: str\n"
        "    gate_inputs_hash: str\n"
        "    gate_version: str\n"
        "    model_pin: str\n"
        "\n"
        "\n"
        "@dataclasses.dataclass\n"
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
        "        return 0\n"
        "\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
        "\n"
        "\n"
        "def _field(value, name):\n"
        "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
        "\n"
        "\n"
        "def _log(op, cache_key):\n"
        "    try:\n"
        "        h = _field(cache_key, 'spec_bundle_hash')\n"
        "    except Exception:\n"
        "        h = None\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps({'op': op, 'spec_bundle_hash': h}) + '\\n')\n"
        "\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _log('get', cache_key)\n"
        "    if HIT_HASH is not None and _field(cache_key, 'spec_bundle_hash') == HIT_HASH:\n"
        "        return CachedResult(gate_type='generator', payload=dict(HIT_PAYLOAD), stored_at='2026-01-01T00:00:00Z')\n"
        "    return Miss()\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _log('put', cache_key)\n"
        "    return None\n"
        "\n"
        "\n"
        "def now_iso():\n"
        "    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return {'entry_count': 0}\n"
        "\n"
        "\n"
        "def main(argv=None):\n"
        "    return 0\n"
    )
    d = repo_root / "gen" / "cache-manager"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cache_manager.py").write_text(source, encoding="utf-8")


def read_log(log_path):
    p = Path(log_path)
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def extract_nonce(prompt):
    m = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt)
    if m:
        return m.group(1)
    m = re.search(r"\b([0-9a-f]{32})\b", prompt)
    assert m, "no nonce found in prompt"
    return m.group(1)


@pytest.fixture
def repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.chdir(root)
    write_component(root)
    return root


def test_hint_mode_miss_returns_candidate_without_writing(repo_root, tmp_path):
    log_path = tmp_path / "cache_calls.log"
    write_fake_cache_manager(repo_root, log_path, None, None)

    calls = []

    def backend(prompt, model, **params):
        calls.append(prompt)
        nonce = extract_nonce(prompt)
        text = (
            "Here is the file.\n"
            + "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            + MOCK_FOO
            + "-----END FILE " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    gen_dir = repo_root / "gen" / SLUG
    before = snapshot(gen_dir)

    result = generator.generate(make_bundle(), MODEL, repo_root=repo_root, llm_backend=backend)

    assert len(calls) >= 1
    files = field(result, "files")
    assert files, "expected the candidate's files in the result"
    assert "foo.py" in files
    assert files["foo.py"].strip() == MOCK_FOO.strip()
    assert field(result, "cache_hit") is False
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None

    after = snapshot(gen_dir)
    assert after == before, "gen/<component>/ must be untouched in hint mode"
    assert (gen_dir / "foo.py").read_text(encoding="utf-8") == EXISTING_FOO

    ops = [entry["op"] for entry in read_log(log_path)]
    assert "put" not in ops, "nothing may be written to the cache in hint mode"


def test_hint_mode_cache_hit_returns_cached_without_model_call(repo_root, tmp_path):
    log_path = tmp_path / "cache_calls.log"
    cached_payload = {
        "component_id": COMPONENT_ID,
        "spec_bundle_hash": SPEC_BUNDLE_HASH,
        "model": MODEL,
        "prompt_version": generator.PROMPT_VERSION,
        "cache_hit": False,
        "files": {"foo.py": CACHED_FOO},
        "model_call_error": None,
        "refused": None,
        "retry_feedback": None,
    }
    write_fake_cache_manager(repo_root, log_path, SPEC_BUNDLE_HASH, cached_payload)

    calls = []

    def backend(prompt, model, **params):
        calls.append(prompt)
        return {"text": "", "model": model, "backend": "mock", "model_call_error": None}

    gen_dir = repo_root / "gen" / SLUG
    before = snapshot(gen_dir)

    result = generator.generate(make_bundle(), MODEL, repo_root=repo_root, llm_backend=backend)

    assert calls == [], "no model call may occur on a cache hit"
    assert field(result, "cache_hit") is True
    files = field(result, "files")
    assert files == {"foo.py": CACHED_FOO}
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None

    after = snapshot(gen_dir)
    assert after == before, "gen/<component>/ must be untouched in hint mode"
    assert (gen_dir / "foo.py").read_text(encoding="utf-8") == EXISTING_FOO

    ops = [entry["op"] for entry in read_log(log_path)]
    assert "get" in ops
    assert "put" not in ops, "nothing may be written to the cache in hint mode"