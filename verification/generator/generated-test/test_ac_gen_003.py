# hotdocs-criterion: sha256:fa999f96e014bcc924e9089e8fb5ea76d2ab421f2046d5d1619c406db4ae1365
import hashlib
import re
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


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


@dataclass
class Bundle:
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
    spec_bundle_parts: dict = dc_field(default_factory=dict)

    def __getitem__(self, key):
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return list(self.__dataclass_fields__.keys())

    def __contains__(self, key):
        return key in self.__dataclass_fields__

    def __iter__(self):
        return iter(self.keys())


def make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(FAKE_PYTHON_ADAPTER, encoding="utf-8")
    comp = repo_root / "specs" / "components" / "widget-maker" / "component.md"
    comp.parent.mkdir(parents=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")
    return repo_root


def make_bundle(label, hint_code=None):
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()
    return Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + digest,
        spec="# Widget Maker\n\nMakes widgets (" + label + ").",
        interface="make_widget() -> int",
        constraints="No network.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="- **Widget** - a thing.",
        hint_code=hint_code,
        spec_bundle_parts={},
    )


def make_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make_widget():\n"
            "    return 1\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def assert_declared_version(prompt, result):
    lines = prompt.split("\n")
    assert "PROMPT_VERSION: " + field(result, "prompt_version") in lines


@pytest.fixture(autouse=True)
def _no_remote_cache(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


def test_frozen_version_constant():
    assert generator.PROMPT_VERSION == "v12"


@pytest.mark.parametrize(
    "label,retry_feedback,hint_code",
    [
        ("cold-plain", None, None),
        ("cold-retry", ["R-WIDGET-002", "R-WIDGET-001"], None),
        ("hint-mode", None, {"widget_maker.py": "def make_widget():\n    return 0\n"}),
    ],
)
def test_prompt_version_matches_frozen_template(tmp_path, label, retry_feedback, hint_code):
    repo_root = make_repo(tmp_path)
    bundle = make_bundle(label, hint_code=hint_code)
    prompts = []
    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        retry_feedback,
        repo_root=repo_root,
        llm_backend=make_backend(prompts),
    )
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert len(prompts) == 1
    assert field(result, "prompt_version") == generator.PROMPT_VERSION
    assert_declared_version(prompts[0], result)


def test_prompt_version_on_cache_hit(tmp_path):
    repo_root = make_repo(tmp_path)
    bundle = make_bundle("cache-hit")
    prompts = []
    backend = make_backend(prompts)
    first = generator.generate(bundle, "claude-sonnet-5", None, repo_root=repo_root, llm_backend=backend)
    assert field(first, "prompt_version") == generator.PROMPT_VERSION
    assert_declared_version(prompts[0], first)
    generator.commit_cache(first, repo_root=repo_root)

    second = generator.generate(bundle, "claude-sonnet-5", None, repo_root=repo_root, llm_backend=backend)
    assert field(second, "cache_hit") is True
    assert len(prompts) == 1
    assert field(second, "prompt_version") == generator.PROMPT_VERSION