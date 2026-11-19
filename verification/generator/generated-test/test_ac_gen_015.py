# hotdocs-criterion: sha256:140e7070f1391cba1445c6abea33397d7dcee315425d4c9ff872a8910f46c903
import json
import re
from pathlib import Path

import generator


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"
MODEL = "mock-model"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle:
    """An object with the SpecBundle fields that also reads as a mapping."""

    def __init__(self, **kwargs):
        self._data = dict(kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)


def make_bundle():
    return Bundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="Widget Maker makes widgets.",
        interface="make_widget() -> str",
        constraints="",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=None,
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
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"python\": \"3.12\"}, "
    "\"lockfile_sha256\": None, \"interpreter\": \"/fake/python\"}\n"
)


def cache_manager_source(marker, log_path, files):
    return (
        "from __future__ import annotations\n"
        "\n"
        "import typing\n"
        "from dataclasses import dataclass\n"
        "\n"
        "MARKER = " + repr(marker) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
        "FILES = " + repr(files) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
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
        "@dataclass\n"
        "class _Origin:\n"
        "    marker: str\n"
        "    extra: typing.Optional[str] = None\n"
        "\n"
        "\n"
        "ORIGIN = _Origin(marker=MARKER)\n"
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
        "def now_iso():\n"
        "    return '2026-01-01T00:00:00Z'\n"
        "\n"
        "\n"
        "def _kfield(key, name):\n"
        "    return key[name] if isinstance(key, dict) else getattr(key, name)\n"
        "\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _log('get ' + ORIGIN.marker)\n"
        "    payload = {\n"
        "        'component_id': " + repr(COMPONENT_ID) + ",\n"
        "        'spec_bundle_hash': _kfield(cache_key, 'spec_bundle_hash'),\n"
        "        'model': _kfield(cache_key, 'model_pin'),\n"
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
        "    return CachedResult(gate_type='generator', payload=payload, stored_at=now_iso())\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _log('put ' + ORIGIN.marker)\n"
        "    return None\n"
        "\n"
        "\n"
        "def stats(*, repo_root=None):\n"
        "    return {'entry_count': 0}\n"
        "\n"
        "\n"
        "def main(argv=None):\n"
        "    return 0\n"
    )


def plant_repo(root, marker, log_path, files):
    comp_dir = root / "specs" / "components" / SLUG
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")

    kind_dir = root / "gen" / "kind-python"
    kind_dir.mkdir(parents=True)
    (kind_dir / "kind_python.py").write_text(PYTHON_ADAPTER, encoding="utf-8")

    cm_dir = root / "gen" / "cache-manager"
    cm_dir.mkdir(parents=True)
    (cm_dir / "cache_manager.py").write_text(
        cache_manager_source(marker, log_path, files), encoding="utf-8"
    )


def make_backend(log_path, marker):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("llm " + marker + "\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make_widget():\n"
            "    return 'llm'\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def read_lines(path):
    if not path.exists():
        return []
    return [l for l in path.read_text(encoding="utf-8").split("\n") if l]


def test_ac_gen_015_per_call_cache_manager_reflects_own_repo_root(tmp_path):
    log_path = tmp_path / "calls.log"

    files_a = {"widget_maker.py": "def make_widget():\n    return 'from-repo-a'\n"}
    files_b = {"widget_maker.py": "def make_widget():\n    return 'from-repo-b'\n"}

    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    plant_repo(repo_a, "A", log_path, files_a)
    plant_repo(repo_b, "B", log_path, files_b)

    result_a = generator.generate(
        make_bundle(), MODEL, repo_root=repo_a, llm_backend=make_backend(log_path, "A")
    )
    lines_after_a = read_lines(log_path)

    result_b = generator.generate(
        make_bundle(), MODEL, repo_root=repo_b, llm_backend=make_backend(log_path, "B")
    )
    lines_after_b = read_lines(log_path)

    # Neither call raised; both reached their own cache-manager and got a hit.
    assert field(result_a, "refused") is None
    assert field(result_a, "model_call_error") is None
    assert field(result_a, "cache_hit") is True
    assert field(result_a, "files") == files_a

    assert field(result_b, "refused") is None
    assert field(result_b, "model_call_error") is None
    assert field(result_b, "cache_hit") is True
    assert field(result_b, "files") == files_b

    # The first call used only repo A's cache-manager code.
    gets_a = [l for l in lines_after_a if l.startswith("get ")]
    assert gets_a, "repo A's cache_manager.get was never called"
    assert all(l == "get A" for l in gets_a), json.dumps(lines_after_a)

    # The second call used only repo B's cache-manager code.
    new_lines = lines_after_b[len(lines_after_a):]
    gets_b = [l for l in new_lines if l.startswith("get ")]
    assert gets_b, "repo B's cache_manager.get was never called"
    assert all(l == "get B" for l in gets_b), json.dumps(new_lines)