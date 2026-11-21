# hotdocs-criterion: sha256:2d068534eb3e4f8434ed57d6a279a47d00098bd6c67414ad6514220a84512d99
import hashlib
import re
from pathlib import Path

import pytest

import generator


PYTHON_ADAPTER_SOURCE = (
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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle(dict):
    """A SpecBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle(spec_bundle_hash):
    return Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash=spec_bundle_hash,
        spec="# Widget Maker\n\nR-WIDGET-001 The module MUST define VALUE.",
        interface="VALUE: int",
        constraints="No network access.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=None,
    )


def plant_repo(repo_root):
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(PYTHON_ADAPTER_SOURCE, encoding="utf-8")
    component_md = repo_root / "specs" / "components" / "widget-maker" / "component.md"
    component_md.parent.mkdir(parents=True, exist_ok=True)
    component_md.write_text(COMPONENT_MD, encoding="utf-8")


def make_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "Here is the component.\n"
            + "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            + "VALUE = 1\n"
            + "-----END FILE " + nonce + "-----\n"
            + "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


@pytest.mark.parametrize(
    "seed",
    [b"widget-maker bundle one", b"widget-maker bundle two"],
)
def test_generation_result_spec_bundle_hash_equals_bundle_hash(tmp_path, monkeypatch, seed):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_repo(repo_root)
    log_path = tmp_path / "backend_calls.log"

    spec_bundle_hash = "sha256:" + hashlib.sha256(seed).hexdigest()
    bundle = make_bundle(spec_bundle_hash)

    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        None,
        repo_root=repo_root,
        llm_backend=make_backend(log_path),
    )

    # The mock model was actually consulted and produced a usable candidate.
    assert log_path.exists()
    assert log_path.read_text(encoding="utf-8").count("call\n") >= 1
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "files")

    # Then clause: the result's spec_bundle_hash equals the bundle's exactly.
    assert field(result, "spec_bundle_hash") == spec_bundle_hash
    assert field(result, "spec_bundle_hash") == bundle.spec_bundle_hash