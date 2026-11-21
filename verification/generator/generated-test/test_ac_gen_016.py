# hotdocs-criterion: sha256:b6563a3c6df7f921ca3d45b5ef1572a05b28dbcdb87d478b1068b1a2a27d3526
import re
from pathlib import Path

import generator


SLUG = "widget-maker"
COMPONENT_ID = "comp-widget-maker"
MODULE = "widget_maker"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle:
    """A SpecBundle-shaped object readable by attribute or as a mapping."""

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
    )

    def __init__(self, **kwargs):
        for name in self._FIELDS:
            setattr(self, name, kwargs[name])

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)


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


def _plant_repo(repo_root):
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(FAKE_PYTHON_ADAPTER, encoding="utf-8")
    comp = repo_root / "specs" / "components" / SLUG / "component.md"
    comp.parent.mkdir(parents=True, exist_ok=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")


def _cold_bundle():
    return Bundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="# Gadget\n\nR-WM-001 -- The thing MUST return a greeting.",
        interface="# Library\n\n```\ngreet() -> str\n```",
        constraints="No network access.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="",
        hint_code=None,
    )


def test_ac_gen_016_prompt_instructs_flat_module_or_package_layout(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_repo(repo_root)

    log_path = tmp_path / "model_calls.log"
    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": " + MODULE + ".py-----\n"
            "def greet():\n"
            "    return 'hi'\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = _cold_bundle()
    result = generator.generate(
        bundle, "mock-model", repo_root=repo_root, llm_backend=mock_backend
    )

    # The mock model was called and recorded what it was sent.
    assert log_path.exists(), "mock model was never called"
    assert len(recorded) == 1
    assert field(result, "refused") is None
    assert field(result, "model_call_error") is None

    prompt = recorded[0]

    # The layout instructions are fixed scaffolding: they precede the bundle sections.
    assert "## SPEC" in prompt.split("\n")
    scaffolding = prompt.split("\n## SPEC\n", 1)[0]

    # None of the layout names come from bundle content.
    bundle_text = "\n".join(
        [bundle.spec, bundle.interface, bundle.constraints, bundle.glossary]
    )
    assert MODULE not in bundle_text

    # Names the real flat module and the package alternative.
    assert MODULE + ".py" in scaffolding
    assert MODULE + "/" in scaffolding
    assert "__init__.py" in scaffolding

    # Directly under gen/<component>/.
    assert "gen/" + SLUG + "/" in scaffolding or "gen/" + SLUG in scaffolding

    # Rules out a deeper (e.g. src/) layout.
    lowered = scaffolding.lower()
    assert any(
        marker in lowered
        for marker in ("src/", "src", "deeper", "nest", "subdirector", "directly")
    ), "prompt does not forbid a deeper layout"