# hotdocs-criterion: sha256:c6b3ca479dae8453ac7cea7b80bdd1695bef2442fc5fd4ae14c72953d2d12efe
import dataclasses
import hashlib
import re
from pathlib import Path

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass
class FakeSpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dataclasses.field(default_factory=dict)
    dependency_context: dict = dataclasses.field(default_factory=dict)
    dependency_usage: dict = dataclasses.field(default_factory=dict)
    vars: dict = dataclasses.field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def __getitem__(self, key):
        names = [f.name for f in dataclasses.fields(self)]
        if key not in names:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return [f.name for f in dataclasses.fields(self)]

    def items(self):
        return [(k, getattr(self, k)) for k in self.keys()]

    def __iter__(self):
        return iter(self.keys())

    def __len__(self):
        return len(self.keys())

    def __contains__(self, key):
        return key in self.keys()


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


def test_generation_result_spec_bundle_hash_equals_bundle_hash(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")

    known_hash = "sha256:" + hashlib.sha256(b"ac-gen-018 widget-maker bundle").hexdigest()
    bundle = FakeSpecBundle(
        component_id="comp-widget-maker",
        spec_bundle_hash=known_hash,
        spec="# Widget Maker\n\nMakes widgets.",
        interface="make_widget() -> str",
        constraints="None.",
        glossary="",
        hint_code=None,
    )

    log_path = tmp_path / "calls.log"

    def mock_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        content = "def make_widget():\n    return \"widget\"\n"
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            + content
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
        bundle,
        "mock-model",
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert log_path.exists(), "mock model was never called"
    assert field(result, "spec_bundle_hash") == bundle.spec_bundle_hash
    assert field(result, "spec_bundle_hash") == known_hash