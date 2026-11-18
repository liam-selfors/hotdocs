# hotdocs-criterion: sha256:1b6ad90e04bd0ce03c3e1a15c9f6ac7482dab7a3207a03c7ea45fcdc20fa8567
import dataclasses
import importlib.util
import json
import re
import sys
from pathlib import Path

import test_author


MODEL = "claude-sonnet-5"

EXPECTED_CONTENT = "import os\n\n\ndef test_fixed():\n    assert os.sep\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


@dataclasses.dataclass
class Bundle:
    component_id: str
    criterion_id: str
    covers: str
    criterion_text: str
    requirement_text: str
    interface: str
    glossary: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)
    module_names: list = dataclasses.field(default_factory=list)

    def __getitem__(self, key):
        if key not in self.keys():
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default) if key in self.keys() else default

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]

    def items(self):
        return [(k, getattr(self, k)) for k in self.keys()]

    def values(self):
        return [getattr(self, k) for k in self.keys()]

    def __contains__(self, key):
        return key in self.keys()

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())


def make_bundle():
    return Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-001",
        covers="R-FOO-001",
        criterion_text="Given x = 2\nWhen foo(x) is called\nThen it returns 4",
        requirement_text="# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


FAKE_CACHE_BODY = (
    "import dataclasses\n"
    "import json\n"
    "import os\n"
    "from datetime import datetime, timezone\n"
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
    "def _f(value, name):\n"
    "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
    "\n"
    "\n"
    "def _plain(v):\n"
    "    if dataclasses.is_dataclass(v) and not isinstance(v, type):\n"
    "        return _plain({f.name: getattr(v, f.name) for f in dataclasses.fields(v)})\n"
    "    if isinstance(v, dict):\n"
    "        return {str(k): _plain(x) for k, x in v.items()}\n"
    "    if isinstance(v, (list, tuple)):\n"
    "        return [_plain(x) for x in v]\n"
    "    if v is None or isinstance(v, (str, int, float, bool)):\n"
    "        return v\n"
    "    if hasattr(v, '__dict__'):\n"
    "        return _plain(vars(v))\n"
    "    return str(v)\n"
    "\n"
    "\n"
    "def _key(cache_key):\n"
    "    return {\n"
    "        'spec_bundle_hash': _f(cache_key, 'spec_bundle_hash'),\n"
    "        'gate_inputs_hash': _f(cache_key, 'gate_inputs_hash'),\n"
    "        'gate_version': _f(cache_key, 'gate_version'),\n"
    "        'model_pin': _f(cache_key, 'model_pin'),\n"
    "    }\n"
    "\n"
    "\n"
    "def _skey(k):\n"
    "    return json.dumps([k['spec_bundle_hash'], k['gate_inputs_hash'], k['gate_version'], k['model_pin']])\n"
    "\n"
    "\n"
    "def _load():\n"
    "    if not os.path.exists(STORE_PATH):\n"
    "        return {}\n"
    "    with open(STORE_PATH, 'r', encoding='utf-8') as fh:\n"
    "        return json.load(fh)\n"
    "\n"
    "\n"
    "def _log(entry):\n"
    "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(json.dumps(entry) + '\\n')\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    k = _plain(_key(cache_key))\n"
    "    store = _load()\n"
    "    entry = store.get(_skey(k))\n"
    "    _log({'op': 'get', 'key': k, 'result': 'hit' if entry else 'miss'})\n"
    "    if entry is None:\n"
    "        return Miss()\n"
    "    return CachedResult(gate_type=entry['gate_type'], payload=entry['payload'], stored_at=entry['stored_at'])\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    k = _plain(_key(cache_key))\n"
    "    gate_type = _f(result, 'gate_type')\n"
    "    payload = _plain(_f(result, 'payload'))\n"
    "    stored_at = _f(result, 'stored_at')\n"
    "    expected_type = k['gate_version'].split('@', 1)[0]\n"
    "    if gate_type != expected_type or gate_type not in _REQUIRED:\n"
    "        raise SchemaValidationError('gate type mismatch')\n"
    "    if not isinstance(payload, dict):\n"
    "        raise SchemaValidationError('payload not a mapping')\n"
    "    for name in _REQUIRED[gate_type]:\n"
    "        if name not in payload:\n"
    "            raise SchemaValidationError('missing ' + name)\n"
    "    store = _load()\n"
    "    entry = {'key': k, 'gate_type': gate_type, 'payload': payload, 'stored_at': stored_at}\n"
    "    store[_skey(k)] = entry\n"
    "    with open(STORE_PATH, 'w', encoding='utf-8') as fh:\n"
    "        json.dump(store, fh)\n"
    "    _log({'op': 'put', 'key': k, 'gate_type': gate_type, 'payload': payload})\n"
    "    return None\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {'entry_count': len(_load())}\n"
    "\n"
    "\n"
    "def main(argv=None):\n"
    "    return 0\n"
)


def write_fake_cache(repo_root, log_path, store_path):
    d = repo_root / "gen" / "cache-manager"
    d.mkdir(parents=True, exist_ok=True)
    source = (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        + "STORE_PATH = " + repr(str(store_path)) + "\n"
        + FAKE_CACHE_BODY
    )
    path = d / "cache_manager.py"
    path.write_text(source, encoding="utf-8")
    return path


def mock_backend(prompt, model, **params):
    m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
    assert m is not None, "prompt carries no BEGIN FILE nonce"
    n = m.group(1)
    text = "-----BEGIN FILE " + n + "-----\n" + EXPECTED_CONTENT + "\n-----END FILE " + n + "-----"
    return {"text": text, "model": model, "backend": "mock", "model_call_error": None}


def payload_file_content(payload):
    f = field(payload, "file")
    if isinstance(f, str):
        return f
    return field(f, "content")


def test_ac_author_005_miss_result_written_to_cache_under_key(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "cache_calls.log"
    store_path = tmp_path / "cache_store.json"
    fake_path = write_fake_cache(repo_root, log_path, store_path)

    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(repo_root)

    # Empty cache precondition.
    assert not store_path.exists()

    bundle = make_bundle()
    result = test_author.author_test(
        bundle, MODEL, 0, repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "model_call_error") is None
    assert field(result, "cache_hit") is False
    returned_content = field(field(result, "file"), "content")
    assert body(returned_content) == EXPECTED_CONTENT

    assert log_path.is_file(), "fake cache-manager was never called"
    calls = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    gets = [c for c in calls if c["op"] == "get"]
    puts = [c for c in calls if c["op"] == "put"]
    assert gets, "cache-manager get was never consulted"
    assert gets[0]["result"] == "miss"
    assert len(puts) == 1, calls
    put_call = puts[0]
    assert calls.index(gets[0]) < calls.index(put_call)

    key = put_call["key"]
    # Stored under the same key that was looked up and missed.
    assert key == gets[0]["key"]
    assert key["gate_version"] == test_author.GATE_VERSION
    assert key["model_pin"] == MODEL
    assert isinstance(key["spec_bundle_hash"], str) and key["spec_bundle_hash"]
    assert isinstance(key["gate_inputs_hash"], str) and key["gate_inputs_hash"]

    assert put_call["gate_type"] == "generated_test"
    payload = put_call["payload"]
    assert field(payload, "component_id") == "comp-foo"
    assert field(payload, "criterion_id") == "AC-FOO-001"
    assert field(payload, "model") == MODEL
    assert body(payload_file_content(payload)) == EXPECTED_CONTENT

    # The cache contains that result under that key afterward.
    saved = sys.modules.get("cache_manager")
    try:
        cm = load_module(fake_path, "cache_manager")
        hit = cm.get(cm.CacheKey(**key), repo_root=repo_root)
        assert not isinstance(hit, cm.Miss)
        assert field(hit, "gate_type") == "generated_test"
        assert body(payload_file_content(field(hit, "payload"))) == EXPECTED_CONTENT
        assert cm.stats(repo_root=repo_root)["entry_count"] == 1
    finally:
        if saved is None:
            sys.modules.pop("cache_manager", None)
        else:
            sys.modules["cache_manager"] = saved