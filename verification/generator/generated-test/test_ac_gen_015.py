# hotdocs-criterion: sha256:a92c2a37354044c355b1077bff2ce2b61c9e845ce6d3216d0762822db79c0b4c
import re
from dataclasses import dataclass, field as dc_field, fields as dc_fields
from pathlib import Path

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

    def __getitem__(self, key):
        if key not in self.keys():
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key) if key in self.keys() else default

    def keys(self):
        return [f.name for f in dc_fields(self)]

    def __contains__(self, key):
        return key in self.keys()

    def items(self):
        return [(k, getattr(self, k)) for k in self.keys()]


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

PYTHON_ADAPTER = (
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


def cache_manager_source(tag, log_path, files):
    return (
        "from __future__ import annotations\n"
        "\n"
        "import time\n"
        "from dataclasses import dataclass\n"
        "\n"
        "TAG = " + repr(tag) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "FILES = " + repr(files) + "\n"
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
        "def _field(value, name):\n"
        "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
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
        "    _log('get:' + TAG)\n"
        "    payload = {\n"
        "        'component_id': 'comp-widget-maker',\n"
        "        'spec_bundle_hash': _field(cache_key, 'spec_bundle_hash'),\n"
        "        'model': _field(cache_key, 'model_pin'),\n"
        "        'prompt_version': 'v12',\n"
        "        'cache_hit': False,\n"
        "        'files': dict(FILES),\n"
        "        'model_call_error': None,\n"
        "        'refused': None,\n"
        "        'retry_feedback': None,\n"
        "        'mode': 'single',\n"
        "        'transcript_sha256': None,\n"
        "        'turns': 1,\n"
        "        'tool_calls': 0,\n"
        "        'isolation': None,\n"
        "    }\n"
        "    return CachedResult(gate_type='generator', payload=payload, stored_at='2026-01-01T00:00:00Z')\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _log('put:' + TAG)\n"
        "\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return {'entry_count': 0}\n"
    )


def make_repo(root, tag, log_path, files):
    (root / "specs" / "components" / "widget-maker").mkdir(parents=True)
    (root / "specs" / "components" / "widget-maker" / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (root / "gen" / "kind-python").mkdir(parents=True)
    (root / "gen" / "kind-python" / "kind_python.py").write_text(PYTHON_ADAPTER, encoding="utf-8")
    (root / "gen" / "cache-manager").mkdir(parents=True)
    (root / "gen" / "cache-manager" / "cache_manager.py").write_text(
        cache_manager_source(tag, log_path, files), encoding="utf-8"
    )


def make_bundle():
    return FakeSpecBundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + "0" * 64,
        spec="Widget maker exposes VALUE.",
        interface="VALUE: str",
        constraints="None.",
    )


def make_backend(llm_log):
    def backend(prompt, model, **params):
        with open(llm_log, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "VALUE = 'mock'\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def read_lines(path):
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_ac_gen_015_per_call_cache_manager_dataclasses_resolve(tmp_path):
    log_path = tmp_path / "cache_log.txt"
    llm_log = tmp_path / "llm_log.txt"

    files_a = {"widget_maker.py": "VALUE = 'from repo A'\n"}
    files_b = {"widget_maker.py": "VALUE = 'from repo B'\n"}

    root_a = tmp_path / "repo_a"
    root_b = tmp_path / "repo_b"
    make_repo(root_a, "A", log_path, files_a)
    make_repo(root_b, "B", log_path, files_b)

    backend = make_backend(llm_log)

    result_a = generator.generate(make_bundle(), "mock-model", repo_root=root_a, llm_backend=backend)
    assert field(result_a, "model_call_error") is None
    assert field(result_a, "refused") is None
    assert field(result_a, "cache_hit") is True
    assert dict(field(result_a, "files")) == files_a
    assert read_lines(log_path) == ["get:A"]

    result_b = generator.generate(make_bundle(), "mock-model", repo_root=root_b, llm_backend=backend)
    assert field(result_b, "model_call_error") is None
    assert field(result_b, "refused") is None
    assert field(result_b, "cache_hit") is True
    assert dict(field(result_b, "files")) == files_b
    assert read_lines(log_path) == ["get:A", "get:B"]

    result_a2 = generator.generate(make_bundle(), "mock-model", repo_root=root_a, llm_backend=backend)
    assert field(result_a2, "model_call_error") is None
    assert field(result_a2, "cache_hit") is True
    assert dict(field(result_a2, "files")) == files_a
    assert read_lines(log_path) == ["get:A", "get:B", "get:A"]

    assert read_lines(llm_log) == []