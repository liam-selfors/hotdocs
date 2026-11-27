# hotdocs-criterion: sha256:4e9421ea42ab9170ff06f6d688d25548b16a39426f4599aef3beb9dc07218649
"""AC-GEN-006: generate() never writes the cache; commit_cache() writes only
a result that has files (and no model_call_error/refused) under the R-GEN-005
key; a committed result makes the next identical generate a cache hit."""

import dataclasses
import hashlib
import json
import re
from pathlib import Path

import pytest

import generator


FAKE_PYTHON_ADAPTER = (
    "from pathlib import Path\n"
    "\n"
    "KIND = \"python\"\n"
    "\n"
    "\n"
    "def layout_errors(code_dir):\n"
    "    return [\"bad.py:1: SyntaxError: x\"] if (Path(code_dir) / \"bad.py\").exists() else []\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"python\": \"3.12\"}, \"lockfile_sha256\": None, \"interpreter\": \"/fake/python\"}\n"
)

COMPONENT_MD = (
    "---\n"
    "id: comp-widget-maker\n"
    "title: Widget Maker\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Widget Maker\n"
)

FAKE_CACHE_MANAGER_BODY = (
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
    "REQUIRED = {\n"
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
    "def _k(key):\n"
    "    return json.dumps([\n"
    "        _f(key, 'spec_bundle_hash'),\n"
    "        _f(key, 'gate_inputs_hash'),\n"
    "        _f(key, 'gate_version'),\n"
    "        _f(key, 'model_pin'),\n"
    "    ])\n"
    "\n"
    "\n"
    "def _load():\n"
    "    p = Path(STORE)\n"
    "    if not p.exists():\n"
    "        return {}\n"
    "    return json.loads(p.read_text(encoding='utf-8'))\n"
    "\n"
    "\n"
    "def _log(line):\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(line + '\\n')\n"
    "\n"
    "\n"
    "def now_iso():\n"
    "    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())\n"
    "\n"
    "\n"
    "def get(cache_key, *, repo_root=None):\n"
    "    _log('get')\n"
    "    try:\n"
    "        entry = _load().get(_k(cache_key))\n"
    "    except Exception:\n"
    "        return Miss()\n"
    "    if entry is None:\n"
    "        return Miss()\n"
    "    return CachedResult(gate_type=entry['gate_type'], payload=entry['payload'], stored_at=entry['stored_at'])\n"
    "\n"
    "\n"
    "def put(cache_key, result, *, repo_root=None):\n"
    "    gate_type = _f(result, 'gate_type')\n"
    "    payload = _f(result, 'payload')\n"
    "    expected = str(_f(cache_key, 'gate_version')).split('@', 1)[0]\n"
    "    if gate_type not in REQUIRED or gate_type != expected:\n"
    "        raise SchemaValidationError('gate_type mismatch')\n"
    "    for name in REQUIRED[gate_type]:\n"
    "        if name not in payload:\n"
    "            raise SchemaValidationError('missing payload key ' + name)\n"
    "    data = _load()\n"
    "    data[_k(cache_key)] = {\n"
    "        'gate_type': gate_type,\n"
    "        'payload': json.loads(json.dumps(dict(payload), default=str)),\n"
    "        'stored_at': str(_f(result, 'stored_at')),\n"
    "    }\n"
    "    Path(STORE).write_text(json.dumps(data), encoding='utf-8')\n"
    "    _log('put')\n"
    "\n"
    "\n"
    "def stats(*, repo_root=None):\n"
    "    return {'entry_count': len(_load())}\n"
)

MODEL = "claude-sonnet-5"
RETRY_FEEDBACK = ["R-WIDGET-002", "R-WIDGET-001"]
FILES = {"widget_maker.py": "VALUE = 1\n\n\ndef make():\n    return VALUE\n"}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle(dict):
    """A SpecBundle-shaped value readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def make_bundle(tag):
    return Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + hashlib.sha256(("ac-gen-006-" + tag).encode("utf-8")).hexdigest(),
        spec="# Widget Maker\n\nMakes widgets.",
        interface="make() -> int",
        constraints="None.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=None,
        spec_bundle_parts={},
    )


def make_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir(parents=True, exist_ok=True)
    adapter = root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(FAKE_PYTHON_ADAPTER, encoding="utf-8")
    comp = root / "specs" / "components" / "widget-maker" / "component.md"
    comp.parent.mkdir(parents=True, exist_ok=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")

    store = tmp_path / "fake_cache_store.json"
    log = tmp_path / "fake_cache_calls.log"
    source = (
        "import dataclasses\n"
        "import json\n"
        "import time\n"
        "from pathlib import Path\n"
        "\n"
        "STORE = " + repr(str(store)) + "\n"
        "LOG = " + repr(str(log)) + "\n"
        + FAKE_CACHE_MANAGER_BODY
    )
    cm = root / "gen" / "cache-manager" / "cache_manager.py"
    cm.parent.mkdir(parents=True, exist_ok=True)
    cm.write_text(source, encoding="utf-8")
    return root, store, log


def store_entries(store):
    if not Path(store).exists():
        return {}
    return json.loads(Path(store).read_text(encoding="utf-8"))


def key_string(bundle):
    digest = hashlib.sha256(
        json.dumps(sorted(RETRY_FEEDBACK or []), sort_keys=True).encode("utf-8")
    ).hexdigest()
    return json.dumps([
        field(bundle, "spec_bundle_hash"),
        "sha256:" + digest,
        generator.GATE_VERSION,
        MODEL,
    ])


def make_ok_backend(log_path, files):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = ""
        for path, content in files.items():
            text += "-----BEGIN FILE " + nonce + ": " + path + "-----\n"
            text += content
            text += "-----END FILE " + nonce + "-----\n"
        text += "-----END REPLY " + nonce + "-----\n"
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def calls(log_path):
    if not Path(log_path).exists():
        return 0
    return len(Path(log_path).read_text(encoding="utf-8").splitlines())


@pytest.fixture(autouse=True)
def _no_remote_store(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def test_generate_does_not_write_cache_and_commit_cache_does(tmp_path):
    repo_root, store, _ = make_repo(tmp_path)
    log_path = tmp_path / "model_calls.log"
    bundle = make_bundle("commit")
    key = key_string(bundle)

    assert store_entries(store) == {}

    result = generator.generate(
        bundle, MODEL, list(RETRY_FEEDBACK),
        repo_root=repo_root, llm_backend=make_ok_backend(log_path, FILES),
    )
    assert calls(log_path) == 1
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False
    assert field(result, "files") == FILES

    # generate itself wrote nothing to the cache.
    assert key not in store_entries(store)
    assert store_entries(store) == {}

    generator.commit_cache(result, repo_root)

    entries = store_entries(store)
    assert key in entries
    assert entries[key]["gate_type"] == "generator"
    assert entries[key]["payload"]["files"] == FILES

    # A second identical generate is a cache hit that never calls the model.
    second = generator.generate(
        bundle, MODEL, list(RETRY_FEEDBACK),
        repo_root=repo_root, llm_backend=make_ok_backend(log_path, FILES),
    )
    assert calls(log_path) == 1
    assert field(second, "cache_hit") is True
    assert field(second, "files") == FILES
    assert field(second, "model_call_error") is None


def test_commit_cache_writes_nothing_for_model_call_error(tmp_path):
    repo_root, store, _ = make_repo(tmp_path)
    log_path = tmp_path / "model_calls.log"
    bundle = make_bundle("error")
    key = key_string(bundle)

    ok = generator.generate(
        bundle, MODEL, list(RETRY_FEEDBACK),
        repo_root=repo_root, llm_backend=make_ok_backend(log_path, FILES),
    )
    assert field(ok, "files") == FILES
    assert store_entries(store) == {}

    failed = dataclasses.replace(
        ok,
        files={},
        model_call_error={"category": "network", "message": "connection failed"},
        refused=None,
        cache_hit=False,
    )
    generator.commit_cache(failed, repo_root)
    assert key not in store_entries(store)
    assert store_entries(store) == {}


def test_commit_cache_ignores_real_failed_generation(tmp_path):
    repo_root, store, _ = make_repo(tmp_path)
    log_path = tmp_path / "model_calls.log"
    bundle = make_bundle("real-failure")
    key = key_string(bundle)

    def failing_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        return {
            "text": None,
            "model": model,
            "backend": "mock",
            "model_call_error": {"category": "rate_limit", "message": "429 from backend"},
        }

    result = generator.generate(
        bundle, MODEL, list(RETRY_FEEDBACK),
        repo_root=repo_root, llm_backend=failing_backend,
    )
    assert calls(log_path) >= 1
    assert field(result, "model_call_error") is not None
    assert field(result, "files") == {}

    generator.commit_cache(result, repo_root)
    assert key not in store_entries(store)
    assert store_entries(store) == {}