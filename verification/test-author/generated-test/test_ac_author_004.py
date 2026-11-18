# hotdocs-criterion: sha256:08b36bfa1c8666da22c7d46d1b524dfe0e3a9d9cf17973bf34ccd3b45b86dcea
import json
import re
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import test_author


MODEL = "claude-sonnet-5"
COMPONENT_ID = "comp-foo"
CRITERION_ID = "AC-FOO-001"
CACHED_CONTENT = "import foo\n\n\ndef test_cached_marker():\n    assert foo.foo(2) == 4"
MOCK_CONTENT = "import foo\n\n\ndef test_fresh_model_marker():\n    assert False"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


@dataclass
class CriterionBundle:
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = dc_field(default_factory=dict)
    module_names: list = dc_field(default_factory=list)

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def __contains__(self, key):
        return key in self.__dataclass_fields__

    def keys(self):
        return list(self.__dataclass_fields__.keys())

    def __iter__(self):
        return iter(self.keys())


def make_bundle():
    return CriterionBundle(
        component_id=COMPONENT_ID,
        criterion_id=CRITERION_ID,
        covers="R-FOO-001",
        criterion_text=(
            "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
            "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```"
        ),
        requirement_text="# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


def write_fake_cache_manager(repo_root, cache_log):
    src = (
        "import json\n"
        "from dataclasses import dataclass\n"
        "from datetime import datetime, timezone\n"
        "\n"
        "LOG_PATH = " + repr(str(cache_log)) + "\n"
        "MODEL = " + repr(MODEL) + "\n"
        "COMPONENT_ID = " + repr(COMPONENT_ID) + "\n"
        "CRITERION_ID = " + repr(CRITERION_ID) + "\n"
        "CONTENT = " + repr(CACHED_CONTENT) + "\n"
        "PATH = " + repr("verification/foo/generated-test/test_ac_foo_001.py") + "\n"
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
        "        return 0\n"
        "\n"
        "    def __repr__(self):\n"
        "        return 'Miss()'\n"
        "\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
        "\n"
        "\n"
        "def _f(value, name):\n"
        "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
        "\n"
        "\n"
        "def _log(record):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(record) + '\\n')\n"
        "\n"
        "\n"
        "def now_iso():\n"
        "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    gv = str(_f(cache_key, 'gate_version'))\n"
        "    mp = _f(cache_key, 'model_pin')\n"
        "    _log({'op': 'get', 'gate_version': gv, 'model_pin': mp})\n"
        "    if gv.split('@', 1)[0] == 'generated_test' and mp == MODEL:\n"
        "        payload = {\n"
        "            'component_id': COMPONENT_ID,\n"
        "            'criterion_id': CRITERION_ID,\n"
        "            'model': MODEL,\n"
        "            'seed': 0,\n"
        "            'prompt_version': 'v1',\n"
        "            'cache_hit': False,\n"
        "            'file': {'path': PATH, 'content': CONTENT},\n"
        "            'model_call_error': None,\n"
        "        }\n"
        "        return CachedResult(gate_type='generated_test', payload=payload, stored_at='2026-01-01T00:00:00Z')\n"
        "    return Miss()\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _log({'op': 'put', 'gate_version': str(_f(cache_key, 'gate_version'))})\n"
        "    return None\n"
        "\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return {'entry_count': 1}\n"
        "\n"
        "\n"
        "def main(argv=None):\n"
        "    return 0\n"
    )
    target_dir = Path(repo_root) / "gen" / "cache-manager"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "cache_manager.py").write_text(src, encoding="utf-8")


def make_backend(model_log):
    def backend(prompt, model, **params):
        with open(model_log, "a", encoding="utf-8") as fh:
            fh.write("called " + str(model) + "\n")
        m = re.search(r"-----BEGIN FILE ([0-9a-f]+)-----", prompt or "")
        n = m.group(1) if m else "0" * 32
        text = "-----BEGIN FILE " + n + "-----\n" + MOCK_CONTENT + "\n-----END FILE " + n + "-----"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_cached_result_returned_and_model_never_called(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    cache_log = tmp_path / "cache_calls.log"
    model_log = tmp_path / "model_calls.log"
    write_fake_cache_manager(repo_root, cache_log)

    result = test_author.author_test(
        make_bundle(),
        MODEL,
        0,
        repo_root=repo_root,
        llm_backend=make_backend(model_log),
    )

    # The mock model was never called.
    model_calls = model_log.read_text(encoding="utf-8") if model_log.exists() else ""
    assert model_calls == "", "model backend was called despite a cache hit: " + model_calls

    # The cache was consulted under a generated_test gate_version for this model.
    assert cache_log.exists(), "cache-manager get was never called"
    records = [json.loads(line) for line in cache_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    gets = [r for r in records if r.get("op") == "get"]
    assert gets, "cache-manager get was never called"
    assert any(
        r["gate_version"].split("@", 1)[0] == "generated_test" and r["model_pin"] == MODEL
        for r in gets
    )

    # The cached result is what is returned.
    assert field(result, "model_call_error") is None
    assert field(result, "cache_hit") is True
    assert field(result, "criterion_id") == CRITERION_ID
    assert field(result, "component_id") == COMPONENT_ID
    file_value = field(result, "file")
    assert file_value is not None
    content = field(file_value, "content")
    assert body(content) == CACHED_CONTENT
    assert body(content) != MOCK_CONTENT