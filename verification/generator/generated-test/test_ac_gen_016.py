# hotdocs-criterion: sha256:a6ea765785710b45127278627c3d76d4d013d69f12cc4baabc55068f820d14a7
import json
import re
from pathlib import Path

import generator


PYTHON_ADAPTER = '''from pathlib import Path

KIND = "python"


def layout_errors(code_dir):
    return ["bad.py:1: SyntaxError: x"] if (Path(code_dir) / "bad.py").exists() else []


def provision(repo_root):
    return {"ok": True, "reason": "", "versions": {"python": "3.12"}, "lockfile_sha256": None, "interpreter": "/fake/python"}
'''

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


class Bundle:
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
        "spec_bundle_parts",
    )

    def __init__(self, **kwargs):
        for name in self._FIELDS:
            setattr(self, name, kwargs[name])

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key) if key in self._FIELDS else default

    def keys(self):
        return list(self._FIELDS)

    def __contains__(self, key):
        return key in self._FIELDS

    def __iter__(self):
        return iter(self._FIELDS)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle():
    return Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + "a" * 64,
        spec="# Widget Maker\n\nMakes widgets.",
        interface="# Library\n\nmake() -> int",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary",
        hint_code=None,
        spec_bundle_parts={},
    )


def test_ac_gen_016_prompt_instructs_flat_module_or_package_layout(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    (repo_root / "gen" / "kind-python").mkdir(parents=True)
    (repo_root / "gen" / "kind-python" / "kind_python.py").write_text(PYTHON_ADAPTER, encoding="utf-8")
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")

    log_path = tmp_path / "prompts.jsonl"

    def mock_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt}) + "\n")
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        nonce = m.group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make():\n"
            "    return 1\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    result = generator.generate(
        make_bundle(), "mock-model", repo_root=repo_root, llm_backend=mock_backend
    )
    assert field(result, "refused") is None

    assert log_path.exists(), "mock model was never called"
    lines = [l for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) >= 1
    prompt = json.loads(lines[0])["prompt"]

    # Only the fixed instructions, which precede every bundle-derived section.
    prompt_lines = prompt.split("\n")
    assert "## SPEC" in prompt_lines
    instructions = "\n".join(prompt_lines[: prompt_lines.index("## SPEC")])

    # Names the real flat module and the package alternative.
    assert "widget_maker.py" in instructions
    assert "widget_maker/" in instructions
    assert "__init__.py" in instructions
    # Directly under gen/<component>/.
    assert "gen/" in instructions
    # Forbids a deeper src/-style layout.
    assert "src" in instructions