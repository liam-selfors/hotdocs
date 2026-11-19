# hotdocs-criterion: sha256:70b0ded720285dc02f790ebbf1d4cccc64021a71efaba740216c2fc605e0fddb
import hashlib
import re
import uuid
from pathlib import Path

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


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _setup_repo(repo_root):
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")
    comp = repo_root / "specs" / "components" / "foo-bar" / "component.md"
    comp.parent.mkdir(parents=True, exist_ok=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")


def _bundle():
    digest = hashlib.sha256(uuid.uuid4().hex.encode("utf-8")).hexdigest()
    return {
        "component_id": "comp-foo-bar",
        "spec_bundle_hash": "sha256:" + digest,
        "spec": "# Foo Bar\n\nProvides foo_bar.",
        "interface": "def foo_bar() -> int",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


REPLY_FILES = {
    "foo-bar/foo_bar.py": "def foo_bar():\n    return 1\n",
    "gen/foo-bar/helpers/__init__.py": "HELPER = 2\n",
    "foo_bar_extra.py": "EXTRA = 3\n",
}


def _mock_backend(prompt, model, **params):
    nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
    parts = []
    for path, content in REPLY_FILES.items():
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


def test_ac_gen_021_strips_redundant_component_prefix(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _setup_repo(repo_root)

    result = generator.generate(
        _bundle(),
        "claude-sonnet-5",
        repo_root=repo_root,
        llm_backend=_mock_backend,
    )

    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None

    out = repo_root / "gen" / "foo-bar"
    assert (out / "foo_bar.py").is_file()
    assert (out / "helpers" / "__init__.py").is_file()
    assert (out / "foo_bar_extra.py").is_file()

    assert (out / "foo_bar.py").read_text(encoding="utf-8") == REPLY_FILES["foo-bar/foo_bar.py"]
    assert (out / "helpers" / "__init__.py").read_text(encoding="utf-8") == REPLY_FILES["gen/foo-bar/helpers/__init__.py"]
    assert (out / "foo_bar_extra.py").read_text(encoding="utf-8") == REPLY_FILES["foo_bar_extra.py"]

    assert not (out / "foo-bar").exists()
    assert not (out / "gen").exists()