# hotdocs-criterion: sha256:9a74875c691ca96ab9feb9be2b45af7634d1b00167803e2328cac5b3c02d1b41
import re
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
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"python\": \"3.12\"}, \"lockfile_sha256\": None, \"interpreter\": \"/fake/python\"}\n"
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


def _plant(repo_root):
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")
    comp = repo_root / "specs" / "components" / "foo-bar" / "component.md"
    comp.parent.mkdir(parents=True, exist_ok=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")


def _bundle():
    return {
        "component_id": "comp-foo-bar",
        "spec_bundle_hash": "sha256:" + "a" * 64,
        "spec": "# Foo Bar\n\nDoes foo bar things.",
        "interface": "# Library\n\n```\nvalue() -> int\n```",
        "constraints": "",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "",
        "hint_code": None,
    }


def test_ac_gen_021_redundant_prefix_stripped(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant(repo_root)

    calls = []

    reply_files = [
        ("foo-bar/foo_bar.py", "VALUE = 1\n"),
        ("gen/foo-bar/helpers/__init__.py", "# helpers\n"),
        ("foo_bar_extra.py", "EXTRA = 2\n"),
    ]

    def mock_backend(prompt, model, **params):
        calls.append(model)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        parts = []
        for path, content in reply_files:
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

    result = generator.generate(
        _bundle(),
        "anthropic:claude-sonnet-5",
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert calls, "mock model was never called"
    assert field(result, "model_call_error") is None, field(result, "model_call_error")
    assert field(result, "refused") is None

    out = repo_root / "gen" / "foo-bar"
    assert (out / "foo_bar.py").is_file()
    assert (out / "helpers" / "__init__.py").is_file()
    assert (out / "foo_bar_extra.py").is_file()
    assert (out / "foo_bar.py").read_text(encoding="utf-8") == "VALUE = 1\n"
    assert (out / "helpers" / "__init__.py").read_text(encoding="utf-8") == "# helpers\n"
    assert (out / "foo_bar_extra.py").read_text(encoding="utf-8") == "EXTRA = 2\n"

    assert not (out / "foo-bar").exists()
    assert not (out / "gen").exists()