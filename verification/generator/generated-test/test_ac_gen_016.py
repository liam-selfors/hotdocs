# hotdocs-criterion: sha256:d80143ef89dfd898a8b2bad8a61c03c3de25c747f2018ee6a21041bba719402e
import re
import uuid
from pathlib import Path

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle(dict):
    """A mapping that also reads by attribute, like SpecBundle."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


COMPONENT_MD = (
    "---\n"
    "id: comp-widget-maker\n"
    "title: Widget Maker\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: false\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Widget Maker\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Makes widgets.\n"
)


def _write_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "widget-maker"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )


def _bundle():
    return Bundle(
        component_id="comp-widget-maker",
        spec_bundle_hash="sha256:" + uuid.uuid4().hex + uuid.uuid4().hex,
        spec="# Widget Maker\n\nMakes things.\n\n# R-WM-001\n\n**R-WM-001** — `make(x)` MUST return `x + 1`.",
        interface="# Library\n\n```\nmake(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


def _scaffold(prompt):
    lines = prompt.split("\n")
    assert "## SPEC" in lines, "prompt has no '## SPEC' section"
    return "\n".join(lines[: lines.index("## SPEC")])


def test_ac_gen_016_prompt_instructs_flat_or_package_layout(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})", prompt)
        nonce = m.group(1) if m else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + ": widget_maker.py-----\n"
            "def make(x):\n"
            "    return x + 1\n"
            "-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = generator.generate(
        _bundle(), "mock-model", repo_root=repo_root, llm_backend=mock_backend
    )

    assert len(recorded) >= 1, "mock model was never called"
    assert field(result, "refused") is None
    assert field(result, "model_call_error") is None

    prompt = recorded[0]
    scaffold = _scaffold(prompt)

    # Names the real module in both permitted shapes.
    assert "widget_maker.py" in scaffold, scaffold
    assert "widget_maker/" in scaffold, scaffold
    assert "__init__.py" in scaffold, scaffold

    # Places the output directly under gen/<component>/.
    assert "gen/widget-maker" in scaffold, scaffold
    assert "gen/comp-widget-maker" not in scaffold, scaffold

    # Forbids a deeper (src/-style) layout.
    lowered = scaffold.lower()
    assert any(
        word in lowered for word in ("src", "deeper", "nested", "subdirector")
    ), scaffold

    # The module name is fixed scaffolding, not bundle content.
    assert "widget_maker" not in prompt[len(scaffold):]