# hotdocs-criterion: sha256:f009f64f7b1a81155acdb5d074e2b2d1760cb8c6883c71b533af9d4ab6d2040b
import re
from pathlib import Path

import pytest

import generator


KIND_PYTHON_SRC = (
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

MODULE_CONTENT = "VALUE = 1\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def plant_python_adapter(repo_root):
    d = Path(repo_root) / "gen" / "kind-python"
    d.mkdir(parents=True, exist_ok=True)
    (d / "kind_python.py").write_text(KIND_PYTHON_SRC, encoding="utf-8")


def make_bundle(dependency_usage):
    return {
        "component_id": "comp-widget-maker",
        "spec_bundle_hash": "sha256:" + "ab" * 32,
        "spec": "# Widget Maker\n\nThe widget maker makes widgets.",
        "interface": "# Library\n\n```\nmake() -> int\n```",
        "constraints": "Keep it small.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": dependency_usage,
        "vars": {},
        "glossary": "- **Widget** - a thing.",
        "hint_code": None,
        "spec_bundle_parts": {},
    }


def make_mock(recorded):
    def backend(prompt, model, **params):
        recorded.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            + MODULE_CONTENT
            + "-----END FILE " + nonce + "-----\n"
            + "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


@pytest.fixture(autouse=True)
def _no_remote_cache(monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)


@pytest.mark.parametrize(
    "dependency_usage",
    [
        {},
        {"comp-bar": "bar.compute(x: int) -> int\n    Compute a number."},
    ],
)
def test_prompt_instructs_dynamic_loads_resolve_from_repo_root(tmp_path, monkeypatch, dependency_usage):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_python_adapter(repo_root)
    monkeypatch.chdir(repo_root)

    recorded = []
    bundle = make_bundle(dependency_usage)
    result = generator.generate(
        bundle, "mock:model", None, repo_root=repo_root, llm_backend=make_mock(recorded)
    )

    assert field(result, "refused") is None
    assert len(recorded) >= 1, "the mock model was never called"
    prompt = recorded[-1]

    # The bundle text deliberately contains none of these terms, so they can
    # only come from the generator's own instruction.
    assert "repo_root" in prompt
    assert "sys.modules" in prompt
    assert "__file__" in prompt
    assert "import" in prompt
    assert "gen/" in prompt
    assert "tool" in prompt.lower()


def test_no_gen_directory_completes_from_tool_root(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    assert not (repo_root / "gen").exists()
    monkeypatch.chdir(repo_root)

    recorded = []
    bundle = make_bundle({})
    result = generator.generate(
        bundle, "mock:model", None, repo_root=repo_root, llm_backend=make_mock(recorded)
    )

    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False
    files = field(result, "files")
    assert files == {"widget_maker.py": MODULE_CONTENT}
    assert len(recorded) == 1
    written = repo_root / "gen" / "widget-maker" / "widget_maker.py"
    assert written.read_text(encoding="utf-8") == MODULE_CONTENT