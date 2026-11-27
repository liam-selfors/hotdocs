# hotdocs-criterion: sha256:7755f2892cf8fdc706348522f33bc19e1e0580f7e400002928c9da8164f14746
import re
from pathlib import Path

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle:
    """An object with the SpecBundle fields that also reads as a mapping."""

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
        "spec_bundle_parts",
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


def make_bundle():
    return Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="# Widget Maker\n\nMakes widgets.",
        interface="make() -> str",
        constraints="",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=None,
        spec_bundle_parts={},
    )


PYTHON_ADAPTER = (
    "from pathlib import Path\n"
    "\n"
    'KIND = "python"\n'
    "\n"
    "\n"
    "def layout_errors(code_dir):\n"
    '    return ["bad.py:1: SyntaxError: x"] if (Path(code_dir) / "bad.py").exists() else []\n'
    "\n"
    "\n"
    "def provision(repo_root):\n"
    '    return {"ok": True, "reason": "", "versions": {"python": "3.12"}, "lockfile_sha256": None, "interpreter": "/fake/python"}\n'
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


def fake_cache_manager_source(marker, log_path):
    # `from __future__ import annotations` makes every annotation a string,
    # so dataclasses must look the module up in sys.modules while each
    # class body is being processed: an unregistered module fails here.
    return (
        "from __future__ import annotations\n"
        "\n"
        "from dataclasses import dataclass\n"
        "from typing import ClassVar\n"
        "\n"
        "MARKER = " + repr(marker) + "\n"
        "LOG = " + repr(str(log_path)) + "\n"
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
        "    KNOWN: ClassVar[tuple] = ('generator', 'compiler', 'generated_test', 'llm_judge', 'license_scanner', 'secret_scanner')\n"
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
        "def _log(line):\n"
        "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "def _attr(value, name):\n"
        "    return value[name] if isinstance(value, dict) else getattr(value, name)\n"
        "\n"
        "\n"
        "def now_iso():\n"
        "    return '2026-01-01T00:00:00Z'\n"
        "\n"
        "\n"
        "def get(cache_key, *, repo_root=None):\n"
        "    _log('get ' + MARKER)\n"
        "    payload = {\n"
        "        'component_id': 'comp-widget-maker',\n"
        "        'model': _attr(cache_key, 'model_pin'),\n"
        "        'prompt_version': 'v12',\n"
        "        'files': {'widget_maker.py': 'MARKER = ' + repr(MARKER) + '\\n'},\n"
        "    }\n"
        "    return CachedResult(gate_type='generator', payload=payload, stored_at=now_iso())\n"
        "\n"
        "\n"
        "def put(cache_key, result, *, repo_root=None):\n"
        "    _log('put ' + MARKER)\n"
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


def plant_repo(repo_root, marker, log_path):
    (repo_root / "gen" / "cache-manager").mkdir(parents=True)
    (repo_root / "gen" / "cache-manager" / "cache_manager.py").write_text(
        fake_cache_manager_source(marker, log_path), encoding="utf-8"
    )
    (repo_root / "gen" / "kind-python").mkdir(parents=True)
    (repo_root / "gen" / "kind-python" / "kind_python.py").write_text(
        PYTHON_ADAPTER, encoding="utf-8"
    )
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")


def make_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "MARKER = 'from-model'\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def test_ac_gen_015_per_call_cache_manager_loads_cleanly_from_each_repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    logs = tmp_path / "logs"
    logs.mkdir()
    log_a = logs / "cache_a.log"
    log_b = logs / "cache_b.log"
    model_log = logs / "model.log"

    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    repo_a.mkdir()
    repo_b.mkdir()
    plant_repo(repo_a, "repo-a", log_a)
    plant_repo(repo_b, "repo-b", log_b)

    backend = make_backend(model_log)

    # Neither call raises: each repo's cache-manager, defining real
    # dataclasses, resolves cleanly.
    result_a = generator.generate(make_bundle(), "mock-model", repo_root=repo_a, llm_backend=backend)
    result_b = generator.generate(make_bundle(), "mock-model", repo_root=repo_b, llm_backend=backend)

    for result in (result_a, result_b):
        assert field(result, "refused") is None
        assert field(result, "model_call_error") is None
        assert field(result, "cache_hit") is True

    # Each call's result came from its own repo_root's cache-manager code.
    assert field(result_a, "files") == {"widget_maker.py": "MARKER = 'repo-a'\n"}
    assert field(result_b, "files") == {"widget_maker.py": "MARKER = 'repo-b'\n"}

    # Each repo's cache-manager ran, and only for its own call.
    assert log_a.exists(), "repo_a's cache-manager was never called"
    assert log_b.exists(), "repo_b's cache-manager was never called"
    lines_a = [l for l in log_a.read_text(encoding="utf-8").splitlines() if l]
    lines_b = [l for l in log_b.read_text(encoding="utf-8").splitlines() if l]
    assert "get repo-a" in lines_a
    assert "get repo-b" in lines_b
    assert all(l.endswith("repo-a") for l in lines_a)
    assert all(l.endswith("repo-b") for l in lines_b)