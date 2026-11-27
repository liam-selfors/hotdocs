# hotdocs-criterion: sha256:decf7dca5a34dbcec31d1576cdb17af23f6241ed6b17d2ef96106495c8017cdd
import re

import generator


KNOWN_HASH = "sha256:" + "0123456789abcdef" * 4

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

FAKE_PYTHON_ADAPTER = '''from pathlib import Path

KIND = "python"


def layout_errors(code_dir):
    return ["bad.py:1: SyntaxError: x"] if (Path(code_dir) / "bad.py").exists() else []


def provision(repo_root):
    return {"ok": True, "reason": "", "versions": {"python": "3.12"}, "lockfile_sha256": None, "interpreter": "/fake/python"}
'''


class Bundle:
    """An object with the SpecBundle fields, readable as attributes or as a mapping."""

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
            setattr(self, name, kwargs[name])

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key) if key in self._FIELDS else default

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def __contains__(self, key):
        return key in self._FIELDS


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle():
    return Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash=KNOWN_HASH,
        spec="# Widget Maker\n\nR-WIDGET-001 — make_widget MUST return 'widget'.",
        interface="make_widget() -> str",
        constraints="No network access.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=None,
        spec_bundle_parts={},
    )


def plant_repo(repo_root):
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(FAKE_PYTHON_ADAPTER, encoding="utf-8")


def test_generation_result_spec_bundle_hash_equals_bundle_hash(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_repo(repo_root)

    calls = []

    def mock_backend(prompt, model, **params):
        calls.append(model)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        reply = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make_widget():\n"
            "    return 'widget'\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": reply,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = make_bundle()
    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    # Preconditions: the mock was reached and produced a usable candidate.
    assert len(calls) == 1
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "files")

    # Then: the result's spec_bundle_hash equals the bundle's own, exactly.
    assert field(result, "spec_bundle_hash") == KNOWN_HASH
    assert field(result, "spec_bundle_hash") == bundle.spec_bundle_hash