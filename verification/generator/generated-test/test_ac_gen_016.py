import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field, fields

import pytest

import generator


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"
MODULE = "widget_maker"


@dataclass
class FakeSpecBundle(Mapping):
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = field(default_factory=dict)
    dependency_context: dict = field(default_factory=dict)
    dependency_usage: dict = field(default_factory=dict)
    vars: dict = field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def __getitem__(self, key):
        names = [f.name for f in fields(self)]
        if key not in names:
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter([f.name for f in fields(self)])

    def __len__(self):
        return len(fields(self))

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


def _get(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _write_component_md(repo_root):
    comp_dir = repo_root / "specs" / "components" / SLUG
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(
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
        "Widget Maker doubles a number.\n",
        encoding="utf-8",
    )
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )


def _make_bundle():
    return FakeSpecBundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec=(
            "# Widget Maker\n\n## Purpose\n\nWidget Maker doubles a number.\n\n"
            "# R-WIDGET-001\n\n**R-WIDGET-001** — `double(x)` MUST return `2 * x`."
        ),
        interface="# Library\n\n```\ndouble(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


def _bundle_text(bundle):
    parts = []
    for name in bundle:
        value = bundle[name]
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            parts.append(json.dumps(value))
    return "\n".join(parts)


def _make_recording_backend(log_path):
    def backend(prompt, model, **params):
        record = {
            "prompt": prompt if isinstance(prompt, str) else str(prompt),
            "model": model,
            "params": {k: (v if isinstance(v, (str, int, float, bool)) or v is None else repr(v))
                       for k, v in params.items()},
        }
        existing = []
        if log_path.exists():
            existing = json.loads(log_path.read_text(encoding="utf-8"))
        existing.append(record)
        log_path.write_text(json.dumps(existing), encoding="utf-8")

        text_prompt = record["prompt"]
        m = re.search(r"BEGIN FILE ([0-9a-f]{32})", text_prompt)
        if m is None:
            m = re.search(r"\b([0-9a-f]{32})\b", text_prompt)
        nonce = m.group(1) if m else "0" * 32
        reply = (
            "Here is the module.\n"
            f"-----BEGIN FILE {nonce}: {MODULE}.py-----\n"
            "def double(x):\n"
            "    return 2 * x\n"
            f"-----END FILE {nonce}-----\n"
        )
        return {
            "text": reply,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_ac_gen_016_prompt_instructs_flat_or_package_layout(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    _write_component_md(repo_root)

    bundle = _make_bundle()
    bundle_text = _bundle_text(bundle)
    # The layout instruction must be fixed scaffolding, never bundle content:
    # make sure none of the strings we look for could have leaked in from the bundle.
    assert MODULE not in bundle_text
    assert "__init__" not in bundle_text
    assert "src" not in bundle_text.lower()

    log_path = tmp_path / "model_calls.json"
    backend = _make_recording_backend(log_path)

    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        repo_root=repo_root,
        llm_backend=backend,
    )

    assert log_path.exists(), (
        "mock model was never called; result: "
        f"model_call_error={_get(result, 'model_call_error')!r}, "
        f"refused={_get(result, 'refused')!r}"
    )
    calls = json.loads(log_path.read_text(encoding="utf-8"))
    assert len(calls) >= 1

    sent = "\n".join(
        c["prompt"] + "\n" + "\n".join(str(v) for v in c["params"].values())
        for c in calls
    )

    # Names the real flat module for comp-widget-maker.
    assert f"{MODULE}.py" in sent, "prompt does not name the flat module widget_maker.py"
    # Names the real package alternative for comp-widget-maker.
    assert f"{MODULE}/" in sent, "prompt does not name the package widget_maker/"
    assert "__init__.py" in sent, "prompt does not mention the package's __init__.py"
    # Forbids a deeper src/-style layout.
    assert "src" in sent.lower(), "prompt does not forbid a deeper src/-style layout"