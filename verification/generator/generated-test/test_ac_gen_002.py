# hotdocs-criterion: sha256:8dc5771f046aa02f9b0b3d6811e267edf62bc3901c4682456b91c2f3059a2b70
"""AC-GEN-002: in hint mode, hint_code reaches the model as its own,
distinctly labeled section, separate from the cold bundle fields."""

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

COLD_HEADINGS = [
    "## SPEC",
    "## INTERFACE",
    "## CONSTRAINTS",
    "## DEPENDENCY INTERFACES",
    "## DEPENDENCY CONTEXT",
    "## VARS",
    "## GLOSSARY",
]


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


class Bundle:
    """An object with the SpecBundle fields, readable as attributes or a mapping."""

    _FIELDS = (
        "component_id", "spec_bundle_hash", "spec", "interface", "constraints",
        "dependency_interfaces", "dependency_context", "dependency_usage",
        "vars", "glossary", "hint_code", "spec_bundle_parts",
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

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)


def _plant_repo(repo_root):
    adapter = repo_root / "gen" / "kind-python" / "kind_python.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text(PYTHON_ADAPTER, encoding="utf-8")
    comp = repo_root / "specs" / "components" / "widget-maker" / "component.md"
    comp.parent.mkdir(parents=True, exist_ok=True)
    comp.write_text(COMPONENT_MD, encoding="utf-8")


def test_ac_gen_002_hint_code_is_its_own_labeled_section(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _plant_repo(repo_root)
    monkeypatch.chdir(tmp_path)

    hint_code = {
        "widget_maker.py": "HINT_MARKER_ALPHA = 1\n",
        "b/zz.py": "HINT_MARKER_BETA = 2\n",
    }
    bundle = Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="COLD_SPEC_MARKER the widget maker makes widgets.",
        interface="COLD_INTERFACE_MARKER make_widget() -> str",
        constraints="COLD_CONSTRAINTS_MARKER no network.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="COLD_GLOSSARY_MARKER widget: a thing.",
        hint_code=hint_code,
        spec_bundle_parts={},
    )

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make_widget():\n"
            "    return 'widget'\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {"text": text, "model": model, "backend": "mock", "model_call_error": None}

    result = generator.generate(
        bundle, "mock-model", repo_root=repo_root, llm_backend=mock_backend
    )

    assert field(result, "refused") is None
    assert len(recorded) == 1, "the mock model must be called exactly once"
    prompt = recorded[0]
    lines = prompt.split("\n")

    # hint_code has its own, distinctly labeled section.
    assert lines.count("## HINT_CODE") == 1
    hint_section = section(prompt, "## HINT_CODE")

    # Each hint file is inside that section, labeled, sorted by path.
    for path, content in hint_code.items():
        begin = "--- hint file: " + path + " ---"
        end = "--- end hint file: " + path + " ---"
        hint_lines = hint_section.split("\n")
        assert begin in hint_lines
        assert end in hint_lines
        b, e = hint_lines.index(begin), hint_lines.index(end)
        assert b < e
        assert content.rstrip("\n") in "\n".join(hint_lines[b + 1:e])
    assert hint_section.index("--- hint file: b/zz.py ---") < hint_section.index(
        "--- hint file: widget_maker.py ---"
    )

    # Hint content appears only in the HINT_CODE section, never mixed into
    # the cold fields' sections.
    for marker in ("HINT_MARKER_ALPHA", "HINT_MARKER_BETA"):
        assert prompt.count(marker) == hint_section.count(marker) == 1

    # The cold bundle fields stay in their own sections, separate from hint_code.
    for heading in COLD_HEADINGS:
        assert heading in lines
        cold = section(prompt, heading)
        assert "HINT_MARKER" not in cold
        assert "--- hint file:" not in cold
    for marker, heading in (
        ("COLD_SPEC_MARKER", "## SPEC"),
        ("COLD_INTERFACE_MARKER", "## INTERFACE"),
        ("COLD_CONSTRAINTS_MARKER", "## CONSTRAINTS"),
        ("COLD_GLOSSARY_MARKER", "## GLOSSARY"),
    ):
        assert marker in section(prompt, heading)
        assert marker not in hint_section

    # The HINT_CODE section comes after the cold sections.
    hint_idx = lines.index("## HINT_CODE")
    for heading in COLD_HEADINGS:
        assert lines.index(heading) < hint_idx