import dataclasses
import hashlib
import json
import re
from pathlib import Path

import pytest

import generator


HINT_MARK = "QQ_HC_MARK_5531"
SPEC_MARK = "QQ_SP_MARK_5531"
IFACE_MARK = "QQ_IF_MARK_5531"
CONSTR_MARK = "QQ_CN_MARK_5531"
GLOSS_MARK = "QQ_GL_MARK_5531"
COLD_MARKS = [SPEC_MARK, IFACE_MARK, CONSTR_MARK, GLOSS_MARK]

HINT_LABEL_RE = re.compile(
    r"(hint"
    r"|existing\s+(code|implementation|files?|source)"
    r"|current\s+(code|implementation|files?|source|contents?)"
    r"|prior\s+(code|implementation)"
    r"|previous\s+(code|implementation))",
    re.IGNORECASE,
)


@dataclasses.dataclass
class FakeSpecBundle:
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
    hint_code: dict = None

    def _names(self):
        return [f.name for f in dataclasses.fields(self)]

    def __getitem__(self, key):
        if key not in self._names():
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self._names():
            return getattr(self, key)
        return default

    def keys(self):
        return list(self._names())

    def values(self):
        return [getattr(self, n) for n in self._names()]

    def items(self):
        return [(n, getattr(self, n)) for n in self._names()]

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())

    def __contains__(self, key):
        return key in self._names()


FAKE_CACHE_MANAGER = '''\
import dataclasses
import datetime


@dataclasses.dataclass
class CacheKey:
    spec_bundle_hash: str
    gate_inputs_hash: str
    gate_version: str
    model_pin: str


@dataclasses.dataclass
class CachedResult:
    gate_type: str
    payload: dict
    stored_at: str


class Miss:
    def __eq__(self, other):
        return isinstance(other, Miss)

    def __hash__(self):
        return hash("Miss")

    def __repr__(self):
        return "Miss()"


class SchemaValidationError(ValueError):
    pass


_REQUIRED = {
    "generator": ["component_id", "model", "prompt_version", "files"],
    "compiler": ["outputs", "gate_version", "summary"],
    "generated_test": ["component_id", "criterion_id", "model", "file"],
    "llm_judge": ["result", "rationale"],
    "license_scanner": ["component_id", "gate_version", "similarity_score", "blocked", "matches"],
    "secret_scanner": ["scope", "gate_version", "flagged", "matches"],
}


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def get(cache_key, *, repo_root=None):
    return Miss()


def put(cache_key, result, *, repo_root=None):
    gate_version = _field(cache_key, "gate_version") or ""
    key_type = gate_version.split("@", 1)[0]
    gate_type = _field(result, "gate_type")
    if gate_type not in _REQUIRED or gate_type != key_type:
        raise SchemaValidationError("gate type mismatch")
    payload = _field(result, "payload")
    if not isinstance(payload, dict):
        raise SchemaValidationError("payload must be a mapping")
    for k in _REQUIRED[gate_type]:
        if k not in payload:
            raise SchemaValidationError("missing payload key: " + k)
    return None


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def stats(*, repo_root=None):
    return {"entry_count": 0}


def main(argv=None):
    return 0
'''


COMPONENT_MD = """---
id: comp-widget
title: Widget
status: draft
owners: [team-a]
sealed: false
depends_on: []
---

# Widget

## Purpose

Widget returns a fixed token.
"""

HINT_FILE_CONTENT = "def widget():\n    return '" + HINT_MARK + "'\n"


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _extract_nonce(prompt):
    m = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt)
    if m:
        return m.group(1)
    m = re.search(r"(?<![0-9a-fA-F])([0-9a-f]{32})(?![0-9a-fA-F])", prompt)
    if m:
        return m.group(1)
    return "0" * 32


def _build_repo(tmp_path):
    repo_root = tmp_path / "repo"
    comp_dir = repo_root / "specs" / "components" / "widget"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(COMPONENT_MD, encoding="utf-8")

    cache_dir = repo_root / "gen" / "cache-manager"
    cache_dir.mkdir(parents=True)
    (cache_dir / "cache_manager.py").write_text(FAKE_CACHE_MANAGER, encoding="utf-8")

    widget_gen = repo_root / "gen" / "widget"
    widget_gen.mkdir(parents=True)
    (widget_gen / "widget.py").write_text(HINT_FILE_CONTENT, encoding="utf-8")
    return repo_root


def _build_bundle():
    spec_text = (
        "# Widget\n\n## Purpose\n\nWidget returns a fixed token " + SPEC_MARK + ".\n\n"
        "# R-WIDGET-001\n\n**R-WIDGET-001** \u2014 `widget()` MUST return a string."
    )
    interface_text = "# Library\n\n```\nwidget() -> str\n```\n\n" + IFACE_MARK
    constraints_text = "# Constraints\n\nNone. " + CONSTR_MARK
    glossary_text = "# Glossary\n\n- **Widget** \u2014 a test term " + GLOSS_MARK + "."
    digest = hashlib.sha256(b"ac-gen-002-hint-mode-bundle").hexdigest()
    return FakeSpecBundle(
        component_id="comp-widget",
        spec_bundle_hash="sha256:" + digest,
        spec=spec_text,
        interface=interface_text,
        constraints=constraints_text,
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary=glossary_text,
        hint_code={"widget.py": HINT_FILE_CONTENT},
    )


def test_ac_gen_002_hint_code_is_distinctly_labeled_section(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    repo_root = _build_repo(tmp_path)
    bundle = _build_bundle()
    log_path = tmp_path / "mock_model_log.jsonl"

    def mock_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        nonce = _extract_nonce(prompt)
        text = (
            "-----BEGIN FILE " + nonce + ": widget.py-----\n"
            "def widget():\n"
            "    return 'ok'\n"
            "-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = generator.generate(
        bundle,
        "anthropic:claude-sonnet-5",
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    refused = _field(result, "refused")
    assert refused is None, "generation was refused unexpectedly: %r" % (refused,)

    assert log_path.is_file(), "mock model was never called"
    records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert records, "mock model recorded no calls"

    prompts = [r["prompt"] for r in records if isinstance(r.get("prompt"), str)]
    assert prompts, "mock model recorded no string prompt"
    prompt = next((p for p in prompts if HINT_MARK in p), None)
    assert prompt is not None, "hint_code content does not appear in any prompt sent to the model"

    # The cold bundle fields are still present in the prompt.
    for mark in COLD_MARKS:
        assert mark in prompt, "cold bundle field marker %s missing from prompt" % mark

    hint_pos = prompt.index(HINT_MARK)

    # Hint content must not be interleaved into a cold field: find the last
    # cold-field content preceding the hint content, and require a distinct
    # hint/existing-code label between that cold content and the hint content.
    preceding_cold = [prompt.rfind(m, 0, hint_pos) for m in COLD_MARKS]
    preceding_cold = [p for p in preceding_cold if p != -1]
    region_start = max(preceding_cold) if preceding_cold else 0
    region = prompt[region_start:hint_pos]

    for mark in COLD_MARKS:
        if mark in region[len(mark):]:
            pytest.fail("cold field content appears between the hint label region and hint_code")

    assert HINT_LABEL_RE.search(region), (
        "hint_code is not preceded by a distinct label separating it from the cold "
        "bundle fields; text between the last cold field and hint_code was:\n%s" % region
    )

    # The hint file's path should be identifiable within the hint section too.
    hint_section_tail = prompt[region_start:hint_pos + len(HINT_MARK)]
    assert "widget.py" in hint_section_tail, (
        "hint_code's relative path is not identified in the labeled hint section"
    )