# hotdocs-criterion: sha256:01996ee49e109dad7a605bb7ee0381d720ad1d79efa7927aad67ceed575cfdc3
import hashlib
import re
import uuid
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


FAKE_PYTHON_ADAPTER = '''from pathlib import Path

KIND = "python"


def layout_errors(code_dir):
    return ["bad.py:1: SyntaxError: x"] if (Path(code_dir) / "bad.py").exists() else []


def provision(repo_root):
    return {"ok": True, "reason": "", "versions": {"python": "3.12"}, "lockfile_sha256": None, "interpreter": "/fake/python"}
'''

COMPONENT_MD = (
    "---\n"
    "id: comp-foo-bar\n"
    "title: Foo Bar\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "sealed: false\n"
    "---\n"
    "\n"
    "# Foo Bar\n"
)


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


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_ac_gen_021_strips_one_redundant_component_prefix(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    _write(repo_root / "gen" / "kind-python" / "kind_python.py", FAKE_PYTHON_ADAPTER)
    _write(repo_root / "specs" / "components" / "foo-bar" / "component.md", COMPONENT_MD)

    log_path = tmp_path / "mock_calls.log"

    reply_files = {
        "foo-bar/foo_bar.py": "VALUE = 1\n",
        "gen/foo-bar/helpers/__init__.py": "HELPER = 2\n",
        "foo_bar_extra.py": "EXTRA = 3\n",
    }

    def mock_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        parts = []
        for path, content in reply_files.items():
            parts.append("-----BEGIN FILE " + nonce + ": " + path + "-----\n")
            parts.append(content)
            parts.append("-----END FILE " + nonce + "-----\n")
        parts.append("-----END REPLY " + nonce + "-----\n")
        return {
            "text": "".join(parts),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle_hash = "sha256:" + hashlib.sha256(uuid.uuid4().hex.encode("utf-8")).hexdigest()
    bundle = FakeSpecBundle(
        component_id="comp-foo-bar",
        spec_bundle_hash=bundle_hash,
        spec="# Foo Bar\n\nA component that does foo bar things.",
        interface="# Library\n\nfoo_bar module.",
        constraints="",
        glossary="",
        hint_code=None,
    )

    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert log_path.exists(), "mock model was never called"
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None

    out = repo_root / "gen" / "foo-bar"
    assert (out / "foo_bar.py").is_file()
    assert (out / "helpers" / "__init__.py").is_file()
    assert (out / "foo_bar_extra.py").is_file()

    assert (out / "foo_bar.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert (out / "helpers" / "__init__.py").read_text(encoding="utf-8") == "HELPER = 2\n"
    assert (out / "foo_bar_extra.py").read_text(encoding="utf-8") == "EXTRA = 3\n"

    nested_component = out / "foo-bar"
    nested_gen = out / "gen"
    assert not nested_component.exists() or not any(nested_component.rglob("*"))
    assert not nested_gen.exists() or not any(nested_gen.rglob("*"))