# hotdocs-criterion: sha256:95524da8e0479be1f47d6898269d30a6a801268dd19520ca150a9aa9960db68a
import dataclasses
import re
from collections.abc import Mapping
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
    "assets: [fake:static/app.txt]\n"
    "---\n"
    "\n"
    "# Widget Maker\n"
)

KIND_FAKE_PY = '''from pathlib import Path

KIND = "fake"


def layout_errors(asset_file):
    return ["bad"] if "bad" in Path(asset_file).read_text(encoding="utf-8") else []


def provision(repo_root):
    if (Path(repo_root) / "NO_ENV").exists():
        return {"ok": False, "reason": "fake needs fakeprog >= 2", "versions": {}, "lockfile_sha256": None}
    return {"ok": True, "reason": "", "versions": {"fakeprog": "2.0.0"}, "lockfile_sha256": None}
'''

KIND_PYTHON_PY = '''from pathlib import Path

KIND = "python"


def layout_errors(code_dir):
    return ["bad.py:1: SyntaxError: x"] if (Path(code_dir) / "bad.py").exists() else []


def provision(repo_root):
    return {"ok": True, "reason": "", "versions": {"python": "3.12"}, "lockfile_sha256": None, "interpreter": "/fake/python"}
'''

DEFINITION_SECTIONS = [
    "Layout",
    "Environment",
    "Surface",
    "Running criteria",
    "Strength check",
    "Test author guidance",
    "Generator guidance",
]


@dataclasses.dataclass
class Bundle(Mapping):
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
    spec_bundle_parts: dict = dataclasses.field(default_factory=dict)

    def __getitem__(self, key):
        if key not in self._keys():
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter(self._keys())

    def __len__(self):
        return len(self._keys())

    def _keys(self):
        return [f.name for f in dataclasses.fields(self)]


def plant_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")

    arch = repo_root / "specs" / "architecture"
    arch.mkdir(parents=True)
    definition = "# Fake\n"
    for name in DEFINITION_SECTIONS:
        definition = definition + "\n## " + name + "\nx\n"
    (arch / "asset-kind-fake.md").write_text(definition, encoding="utf-8")

    fake_dir = repo_root / "gen" / "kind-fake"
    fake_dir.mkdir(parents=True)
    (fake_dir / "kind_fake.py").write_text(KIND_FAKE_PY, encoding="utf-8")

    py_dir = repo_root / "gen" / "kind-python"
    py_dir.mkdir(parents=True)
    (py_dir / "kind_python.py").write_text(KIND_PYTHON_PY, encoding="utf-8")


def make_backend(log_path, prompt_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        with open(prompt_path, "w", encoding="utf-8") as fh:
            fh.write(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make():\n"
            "    return 1\n"
            "-----END FILE " + nonce + "-----\n"
            "-----BEGIN FILE " + nonce + ": static/app.txt-----\n"
            "ok\n"
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


def test_prompt_names_module_and_assets_before_spec(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    plant_fixture(repo_root)

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "calls.log"
    prompt_path = log_dir / "prompt.txt"

    bundle = Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="Widget Maker makes widgets.",
        interface="make() -> int",
        constraints="None.",
        glossary="Widget: a thing.",
    )

    generator.generate(
        bundle,
        "mock-model",
        repo_root=repo_root,
        llm_backend=make_backend(log_path, prompt_path),
    )

    assert log_path.exists(), "mock model was never called"
    assert log_path.read_text(encoding="utf-8").count("call\n") >= 1

    prompt = prompt_path.read_text(encoding="utf-8")
    lines = prompt.split("\n")
    assert "## SPEC" in lines, "prompt has no '## SPEC' line"
    spec_index = lines.index("## SPEC")
    before = "\n".join(lines[:spec_index])

    assert "widget_maker.py" in before
    assert "static/app.txt" in before