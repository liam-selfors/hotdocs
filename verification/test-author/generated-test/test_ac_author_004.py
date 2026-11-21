# hotdocs-criterion: sha256:9332fc223da4e57c33023454df516330845b06953c888e1dd974088ccbf673bf
import json
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


COMPONENT_ID = "comp-widget-maker"
CRITERION_ID = "AC-WIDGET-MAKER-004"
CACHED_PATH = "verification/widget-maker/generated-test/test_ac_widget_maker_004.py"
CACHED_CONTENT = (
    "import widget_maker\n"
    "\n"
    "\n"
    "def test_cached_widget():\n"
    "    assert widget_maker.make() is not None\n"
)


def _write_fake_cache_manager(repo_root, log_path):
    src = (
        "import dataclasses\n"
        "import json\n"
        "from datetime import datetime, timezone\n"
        "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "CONTENT = " + repr(CACHED_CONTENT) + "\n"
        "PATH = " + repr(CACHED_PATH) + "\n"
        "COMPONENT_ID = " + repr(COMPONENT_ID) + "\n"
        "CRITERION_ID = " + repr(CRITERION_ID) + "\n"
        "\n"
        "\n"
        "class SchemaValidationError(ValueError):\n"
        "    pass\n"
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
        "def _f(value, name):\n"
        "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
        "\n"
        "\n"
        "def _log(entry):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(entry) + '\\n')\n"
        "\n"
        "\n"
        "def now_iso():\n"
        "    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')\n"
        "\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return {'entry_count': 1}\n"
        "\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    gv = str(_f(cache_key, 'gate_version'))\n"
        "    mp = str(_f(cache_key, 'model_pin'))\n"
        "    _log({'op': 'get', 'gate_version': gv, 'model_pin': mp})\n"
        "    if gv.split('@')[0] == 'generated_test' and mp == 'mock':\n"
        "        payload = {\n"
        "            'component_id': COMPONENT_ID,\n"
        "            'criterion_id': CRITERION_ID,\n"
        "            'model': 'mock',\n"
        "            'seed': 0,\n"
        "            'prompt_version': 'v1',\n"
        "            'cache_hit': False,\n"
        "            'file': {'path': PATH, 'content': CONTENT},\n"
        "            'model_call_error': None,\n"
        "            'repair_attempts': 0,\n"
        "            'probe_findings': [],\n"
        "        }\n"
        "        return CachedResult(gate_type='generated_test', payload=payload,\n"
        "                            stored_at='2026-01-01T00:00:00Z')\n"
        "    return Miss()\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    gv = str(_f(cache_key, 'gate_version'))\n"
        "    _log({'op': 'put', 'gate_version': gv})\n"
        "    if gv.split('@')[0] != _f(result, 'gate_type'):\n"
        "        raise SchemaValidationError('gate_type mismatch')\n"
    )
    d = repo_root / "gen" / "cache-manager"
    d.mkdir(parents=True, exist_ok=True)
    (d / "cache_manager.py").write_text(src, encoding="utf-8")


def _write_probe_stand_in(repo_root, log_path):
    src = (
        "LOG = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write('probe\\n')\n"
        "    return _Report()\n"
    )
    d = repo_root / "gen" / "test-probe"
    d.mkdir(parents=True, exist_ok=True)
    (d / "test_probe.py").write_text(src, encoding="utf-8")


def test_cache_hit_returns_cached_result_without_calling_model(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    cache_log = tmp_path / "cache_calls.log"
    probe_log = tmp_path / "probe_calls.log"
    model_log = tmp_path / "model_calls.log"
    cache_log.write_text("", encoding="utf-8")
    probe_log.write_text("", encoding="utf-8")
    model_log.write_text("", encoding="utf-8")

    _write_fake_cache_manager(repo_root, cache_log)
    _write_probe_stand_in(repo_root, probe_log)

    def mock_backend(prompt, model, **params):
        with open(model_log, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        nonces = re.findall(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        n = nonces[-1] if nonces else "0" * 32
        return {
            "text": "-----BEGIN FILE " + n + "-----\nFRESH\n-----END FILE " + n + "-----",
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": "R-WIDGET-MAKER-004",
        "criterion_text": "Given a widget\nWhen make is called\nThen a widget is returned",
        "requirement_text": "R-WIDGET-MAKER-004 - make MUST return a widget.",
        "interface": "make() -> Widget",
        "glossary": "",
        "dependency_interfaces": {},
    }

    result = test_author.author_test(
        bundle, "mock", 0, repo_root=repo_root, llm_backend=mock_backend
    )

    # The mock model is never called.
    assert model_log.read_text(encoding="utf-8") == ""

    # The cache was consulted with a generated_test-typed key for this model.
    entries = [
        json.loads(line)
        for line in cache_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    gets = [e for e in entries if e["op"] == "get"]
    assert gets, "cache-manager get was never called"
    assert any(
        e["gate_version"].split("@")[0] == "generated_test" and e["model_pin"] == "mock"
        for e in gets
    )

    # The cached result is returned.
    assert field(result, "cache_hit") is True
    assert field(result, "model_call_error") is None
    assert field(result, "component_id") == COMPONENT_ID
    assert field(result, "criterion_id") == CRITERION_ID
    assert field(result, "repair_attempts") == 0
    assert list(field(result, "probe_findings")) == []

    f = field(result, "file")
    assert f is not None
    assert field(f, "path") == CACHED_PATH
    content = field(f, "content")
    assert content.splitlines()[0].startswith("# hotdocs-criterion: sha256:")
    assert body(content) == CACHED_CONTENT