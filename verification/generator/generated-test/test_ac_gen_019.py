# hotdocs-criterion: sha256:21a36744c9bcc69cb565a86130f1d3fdb9e4caf295f6d57ceaa04804592b42da
import hashlib
import re
from pathlib import Path

import pytest

import generator


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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle(dict):
    """A mapping that also exposes its keys as attributes."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def make_bundle(tag):
    digest = hashlib.sha256(("ac-gen-019-" + tag).encode("utf-8")).hexdigest()
    return Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + digest,
        spec="Widget Maker makes widgets.\n\nR-WIDGET-001: make() returns 1.",
        interface="make() -> int",
        constraints="Keep it small.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="Widget: a thing.",
        hint_code=None,
    )


def make_backend(calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make():\n"
            "    return 1\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_prompt_instructs_dynamic_loads_resolve_from_repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")

    calls = []
    bundle = make_bundle("prompt")
    generator.generate(
        bundle, "mock-model", repo_root=repo_root, llm_backend=make_backend(calls)
    )

    assert len(calls) == 1
    prompt = calls[0]

    # The bundle itself mentions none of these terms, so they come from the
    # prompt's own instructions.
    assert "sys.modules" in prompt
    assert "__file__" in prompt
    assert "repo_root" in prompt
    assert re.search(r"\bimport\b", prompt)
    assert re.search(r"tool[ _]root", prompt, re.IGNORECASE)

    paragraphs = re.split(r"\n\s*\n", prompt)
    assert any(
        "sys.modules" in p and "__file__" in p and "repo_root" in p
        for p in paragraphs
    ), "no single instruction ties sys.modules, __file__ and repo_root together"


def test_generate_completes_without_gen_dir_in_repo_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    assert not (repo_root / "gen").exists()

    calls = []
    bundle = make_bundle("no-gen")
    result = generator.generate(
        bundle, "mock-model", repo_root=repo_root, llm_backend=make_backend(calls)
    )

    assert result is not None
    assert len(calls) == 1
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    files = field(result, "files")
    assert files
    assert any(path.endswith("widget_maker.py") for path in files)