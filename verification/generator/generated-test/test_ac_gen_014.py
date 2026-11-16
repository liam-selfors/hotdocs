import json
import re
from dataclasses import dataclass, field as dc_field
from pathlib import Path

import pytest

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclass(frozen=True)
class FakeSpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dc_field(default_factory=dict)
    dependency_context: dict = dc_field(default_factory=dict)
    dependency_usage: dict = dc_field(default_factory=dict)
    vars: dict = dc_field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

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

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self._FIELDS:
            return getattr(self, key)
        return default

    def keys(self):
        return list(self._FIELDS)

    def items(self):
        return [(k, getattr(self, k)) for k in self._FIELDS]

    def values(self):
        return [getattr(self, k) for k in self._FIELDS]

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def __contains__(self, key):
        return key in self._FIELDS


USAGE_MARKER = "USAGEMARKER_7f3a"
INTERFACE_MARKER = "IFACEMARKER_9c1d"

USAGE_TEXT = (
    "Module: bar_real_mod (importable as `import bar_real_mod`)\n\n"
    "def triple(x: int) -> int\n"
    "    \"\"\"Return three times x. " + USAGE_MARKER + "\"\"\""
)

INTERFACE_TEXT = (
    "# Library\n\n"
    "```\n"
    "triple(x: int) -> int\n"
    "```\n\n"
    "Contract note " + INTERFACE_MARKER + "."
)


def _bundle():
    return FakeSpecBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec=(
            "# Foo\n\n## Purpose\n\nFoo doubles a number using bar.\n\n"
            "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`."
        ),
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={"comp-bar": INTERFACE_TEXT},
        dependency_context={"comp-bar": "Bar triples a number."},
        dependency_usage={"comp-bar": USAGE_TEXT},
        vars={},
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


def test_ac_gen_014_dependency_usage_is_its_own_labeled_section(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    log_path = tmp_path / "mock_calls.jsonl"

    def mock_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        nonce = m.group(1) if m else "0" * 32
        text = (
            f"-----BEGIN FILE {nonce}: foo.py-----\n"
            "def foo(x):\n"
            "    return 2 * x\n"
            f"-----END FILE {nonce}-----\n"
            f"-----END REPLY {nonce}-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = _bundle()
    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        None,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    # Absence of error/refusal is not the criterion, but a model call must happen.
    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False

    assert log_path.is_file(), "mock model was never called"
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(records) == 1
    prompt = records[0]["prompt"]

    # The recorded input contains the dependency_usage content.
    assert USAGE_MARKER in prompt
    assert INTERFACE_MARKER in prompt

    # Identify the sections generate uses for its prompt.
    sections = generator.render_prompt_sections(bundle)
    sections = [(str(t), str(x)) for t, x in sections]

    usage_sections = [(t, x) for t, x in sections if USAGE_MARKER in x]
    iface_sections = [(t, x) for t, x in sections if INTERFACE_MARKER in x]
    assert usage_sections, "no prompt section carries dependency_usage content"
    assert iface_sections, "no prompt section carries dependency_interfaces content"

    # Never merged: the usage section carries no interface content, and vice versa.
    for t, x in usage_sections:
        assert INTERFACE_MARKER not in x, f"dependency_usage merged with dependency_interfaces in section {t!r}"
        assert t.strip(), "dependency_usage section has no label"
    for t, x in iface_sections:
        assert USAGE_MARKER not in x, f"dependency_interfaces merged with dependency_usage in section {t!r}"

    usage_titles = {t.strip() for t, _ in usage_sections}
    iface_titles = {t.strip() for t, _ in iface_sections}
    assert usage_titles.isdisjoint(iface_titles), "dependency_usage is not distinctly labeled"

    # Those distinctly labeled sections are what the model actually received.
    for t, x in usage_sections + iface_sections:
        assert t.strip() in prompt, f"section label {t!r} missing from model input"
        assert x.strip() in prompt, f"section {t!r} text missing from model input"

    # In the recorded prompt, the usage content follows its own label, and
    # the nearest preceding section label is the usage label, not the interfaces one.
    titles_in_prompt = [(prompt.find(t.strip()), t.strip()) for t, _ in sections if t.strip() in prompt]
    usage_pos = prompt.find(USAGE_MARKER)
    preceding = [(pos, t) for pos, t in titles_in_prompt if 0 <= pos < usage_pos]
    assert preceding, "dependency_usage content appears before any section label"
    nearest_title = max(preceding)[1]
    assert nearest_title in usage_titles
    assert nearest_title not in iface_titles