# hotdocs-criterion: sha256:1b522704a91cab90534a413ffe5c9fac74f50b727b3b4c87f293ea0bdb45d2c3
"""AC-GEN-022 (covers R-GEN-020): the prompt tells the model to implement
exactly what the spec requires and nothing more, and mentions mutation
testing."""

import re
from pathlib import Path

import generator


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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle():
    return Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="# Widget Maker\n\nMakes widgets.",
        interface="# Library\n\n```\nmake() -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Widget** - a thing.",
        hint_code=None,
        spec_bundle_parts={},
    )


def test_prompt_contains_nothing_more_and_mutation_testing(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    repo_root = tmp_path / "repo"
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")

    prompts = []

    def mock_backend(prompt, model, **params):
        prompts.append(prompt)
        match = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        assert match is not None, "prompt does not show the begin marker with a nonce"
        nonce = match.group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            + "def make():\n"
            + "    return 1\n"
            + "-----END FILE " + nonce + "-----\n"
            + "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = generator.generate(
        make_bundle(),
        "mock:model",
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert field(result, "cache_hit") is False
    assert len(prompts) >= 1, "the mock model was never called"

    prompt = prompts[0]
    assert "nothing more" in prompt
    assert "mutation testing" in prompt