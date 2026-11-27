# hotdocs-criterion: sha256:d5349b664ce12aa490d40c1e4dede973a64d97dd470b1e648f1215093e5a88d2
import json
import re
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import pytest

import generator


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclass
class FakeSpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str = ""
    interface: str = ""
    constraints: str = ""
    dependency_interfaces: dict = dc_field(default_factory=dict)
    dependency_context: dict = dc_field(default_factory=dict)
    dependency_usage: dict = dc_field(default_factory=dict)
    vars: dict = dc_field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None
    spec_bundle_parts: dict = dc_field(default_factory=dict)

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return list(self.__dataclass_fields__.keys())

    def __contains__(self, key):
        return key in self.__dataclass_fields__


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


def plant_python_adapter(repo_root):
    path = repo_root / "gen" / "kind-python" / "kind_python.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(FAKE_PYTHON_ADAPTER, encoding="utf-8")


def write_component_md(repo_root, sealed, source_path=None):
    lines = [
        "---",
        "id: " + COMPONENT_ID,
        "title: Widget Maker",
        "status: draft",
        "owners: [pipeline-team]",
        "depends_on: []",
        "sealed: " + ("true" if sealed else "false"),
    ]
    if source_path is not None:
        lines.append("source_path: " + source_path)
    lines += ["---", "", "# Widget Maker", ""]
    path = repo_root / "specs" / "components" / SLUG / "component.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def make_bundle():
    return FakeSpecBundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="# Widget Maker\n\nMakes widgets.",
        interface="# Library\n\nmake_widget() -> str",
        constraints="",
        glossary="",
    )


def make_mock_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        nonce = m.group(1) if m else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make_widget():\n"
            "    return 'w'\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    return backend


def setup_sealed(repo_root):
    write_component_md(repo_root, sealed=True, source_path="legacy/widget/")
    legacy = repo_root / "legacy" / "widget"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "widget.py").write_text("X = 1\n", encoding="utf-8")


def setup_pinned(repo_root):
    write_component_md(repo_root, sealed=False)
    gen_dir = repo_root / "gen" / SLUG
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / "widget_maker.py").write_text("# hand-pinned\n", encoding="utf-8")
    (gen_dir / ".overrides.json").write_text(json.dumps(["widget_maker.py"]), encoding="utf-8")


@pytest.mark.parametrize(
    "setup, expected_reason",
    [
        (setup_sealed, "sealed-component"),
        (setup_pinned, "pinned-override"),
    ],
    ids=["sealed", "pinned-override"],
)
def test_generate_refuses_exempt_component_without_model_call(tmp_path, monkeypatch, setup, expected_reason):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    plant_python_adapter(repo_root)
    setup(repo_root)

    log_path = tmp_path / "model_calls.log"
    backend = make_mock_backend(log_path)

    pinned_path = repo_root / "gen" / SLUG / "widget_maker.py"
    pinned_before = pinned_path.read_text(encoding="utf-8") if pinned_path.exists() else None

    result = generator.generate(
        make_bundle(),
        "mock:model",
        None,
        repo_root=repo_root,
        llm_backend=backend,
    )

    # The mock model is never called.
    assert not log_path.exists() or log_path.read_text(encoding="utf-8") == ""

    files = field(result, "files")
    assert files == {}
    assert field(result, "model_call_error") is None

    refused = field(result, "refused")
    assert isinstance(refused, str)
    assert refused
    assert expected_reason in refused

    # Nothing was overwritten.
    if pinned_before is not None:
        assert pinned_path.read_text(encoding="utf-8") == pinned_before