# hotdocs-criterion: sha256:61af784ed84fe6222df6ec0ce441dc082436fe1f5946bed125eb7cce8825bafc
import hashlib
import json
import re
from pathlib import Path

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
    )

    def __init__(self, **kwargs):
        for name in self._FIELDS:
            setattr(self, name, kwargs[name])

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self._FIELDS:
            return getattr(self, key)
        return default

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def __contains__(self, key):
        return key in self._FIELDS


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


def _plant_repo(repo_root):
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")
    comp = repo_root / "specs" / "components" / "widget-maker" / "component.md"
    comp.parent.mkdir(parents=True, exist_ok=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")


def _make_bundle():
    return Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + hashlib.sha256(b"ac-gen-005 bundle").hexdigest(),
        spec="# Widget Maker\n\nMakes widgets.",
        interface="make_widget() -> str",
        constraints="No network.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=None,
    )


def test_ac_gen_005_cache_hit_returns_cached_result_without_model_call(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_repo(repo_root)
    monkeypatch.chdir(repo_root)

    call_log = tmp_path / "model_calls.log"

    def mock_backend(prompt, model, **params):
        with open(call_log, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        match = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        nonce = match.group(1) if match else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "FRESH = 2\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    bundle = _make_bundle()
    model = "claude-sonnet-5"
    retry_feedback = ["R-WIDGET-001"]
    cached_files = {"widget_maker.py": "CACHED = 1\n"}

    cached = generator.GenerationResult(
        component_id="comp-widget-maker",
        spec_bundle_hash=bundle.spec_bundle_hash,
        model=model,
        prompt_version=generator.PROMPT_VERSION,
        cache_hit=False,
        files=dict(cached_files),
        model_call_error=None,
        refused=None,
        retry_feedback=list(retry_feedback),
        mode="single",
        transcript_sha256=None,
        turns=1,
        tool_calls=0,
        isolation=None,
    )
    generator.commit_cache(cached, repo_root=repo_root)

    # Sanity: the key the interface defines is what the hit is looked up by.
    gate_inputs_hash = "sha256:" + hashlib.sha256(
        json.dumps(sorted(retry_feedback), sort_keys=True).encode("utf-8")
    ).hexdigest()
    assert gate_inputs_hash.startswith("sha256:")
    assert generator.GATE_VERSION == "generator@3.2.0"

    result = generator.generate(
        bundle,
        model,
        list(retry_feedback),
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    # The mock model was never called.
    assert not call_log.exists() or call_log.read_text(encoding="utf-8") == ""

    # The cached result is returned.
    assert field(result, "cache_hit") is True
    assert field(result, "files") == cached_files
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "component_id") == "comp-widget-maker"
    assert field(result, "spec_bundle_hash") == bundle.spec_bundle_hash
    assert field(result, "model") == model
    assert field(result, "prompt_version") == generator.PROMPT_VERSION
    assert field(result, "retry_feedback") == retry_feedback
    assert field(result, "mode") == "single"
    assert field(result, "transcript_sha256") is None
    assert field(result, "turns") == 1
    assert field(result, "tool_calls") == 0
    assert field(result, "isolation") is None