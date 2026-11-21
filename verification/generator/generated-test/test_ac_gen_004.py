# hotdocs-criterion: sha256:1fc07522960572f43af0d0305e27fb4715f84bdba074c66c1261fffded22f247
import re
from pathlib import Path

import generator


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
    "    return {\"ok\": True, \"reason\": \"\", \"versions\": {\"python\": \"3.12\"}, "
    "\"lockfile_sha256\": None, \"interpreter\": \"/fake/python\"}\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle:
    def __init__(self, **kwargs):
        self._data = dict(kwargs)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __contains__(self, key):
        return key in self._data

    def keys(self):
        return self._data.keys()


def make_bundle():
    return Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="# Widget Maker\n\nMakes widgets.",
        interface="make_widget() -> int",
        constraints="No network.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=None,
    )


def plant_repo(repo_root):
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    adapter_dir = repo_root / "gen" / "kind-python"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "kind_python.py").write_text(FAKE_PYTHON_ADAPTER, encoding="utf-8")


def make_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(model + "\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make_widget():\n"
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


def test_ac_gen_004_model_identifier_passed_through(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_repo(repo_root)
    log_path = tmp_path / "calls.log"

    bundle = make_bundle()
    backend = make_backend(log_path)

    model_a = "mock-model-alpha"
    model_b = "mock-model-beta"

    result_a = generator.generate(bundle, model_a, repo_root=repo_root, llm_backend=backend)
    lines_after_a = log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []
    assert lines_after_a == [model_a], (
        "mock model call for first generate did not receive " + repr(model_a)
        + "; got " + repr(lines_after_a)
        + "; result model_call_error=" + repr(field(result_a, "model_call_error"))
        + " refused=" + repr(field(result_a, "refused"))
    )

    result_b = generator.generate(bundle, model_b, repo_root=repo_root, llm_backend=backend)
    lines_after_b = log_path.read_text(encoding="utf-8").splitlines()
    assert lines_after_b == [model_a, model_b], (
        "mock model call for second generate did not receive " + repr(model_b)
        + "; got " + repr(lines_after_b)
        + "; result model_call_error=" + repr(field(result_b, "model_call_error"))
        + " refused=" + repr(field(result_b, "refused"))
    )

    assert field(result_a, "model") == model_a
    assert field(result_b, "model") == model_b