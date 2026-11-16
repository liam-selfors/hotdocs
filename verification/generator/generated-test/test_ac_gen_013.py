"""AC-GEN-013 (Covers: R-GEN-012).

Given a cold-mode SpecBundle, retry_feedback=["R-FOO-003"], and a mock
model that records what it was sent, when generate is called, then the
mock's recorded input contains retry_feedback as a distinctly labeled
section containing only "R-FOO-003" (no Gherkin text, rationale, or
expected/actual values anywhere in the prompt), and the resulting
GenerationResult's retry_feedback echoes ["R-FOO-003"].
"""

import generator

import dataclasses
import hashlib
import json
import re
from collections.abc import Mapping
from pathlib import Path

import pytest


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


@dataclasses.dataclass
class FakeSpecBundle(Mapping):
    """Mirrors SpecBundle's documented fields, in order, readable both by
    attribute and as a read-only mapping."""

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

    def __getitem__(self, key):
        if key not in self._names():
            raise KeyError(key)
        return getattr(self, key)

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())

    def _names(self):
        return [f.name for f in dataclasses.fields(self)]


# Acceptance-only sentinels: they live on disk under the fixture's
# acceptance/ directory, never in the bundle, and must never reach the model.
GHERKIN_SENTINEL = "Given zorblax quantity = 777"
WHEN_SENTINEL = "When frobnicate_quux(zorblax) is called"
THEN_SENTINEL = "Then it returns 9931"
RATIONALE_SENTINEL = "rationale: plinth-vortex-rationale-5521"
EXPECTED_SENTINEL = "expected 9931 but got 1554"

SENTINELS = [
    GHERKIN_SENTINEL,
    WHEN_SENTINEL,
    THEN_SENTINEL,
    RATIONALE_SENTINEL,
    EXPECTED_SENTINEL,
    "9931",
    "1554",
    "zorblax",
    "plinth-vortex",
]

R_ID_RE = re.compile(r"R-[A-Z0-9]+-\d+")


def _make_bundle():
    spec = (
        "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
        "# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`."
    )
    digest = hashlib.sha256(spec.encode("utf-8")).hexdigest()
    return FakeSpecBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + digest,
        spec=spec,
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


def _write_acceptance_decoy(repo_root: Path):
    acc_dir = repo_root / "specs" / "components" / "foo" / "acceptance"
    acc_dir.mkdir(parents=True, exist_ok=True)
    (acc_dir / "AC-FOO-003.md").write_text(
        "# AC-FOO-003\n\n"
        "Covers: R-FOO-003\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        f"{GHERKIN_SENTINEL}\n"
        f"{WHEN_SENTINEL}\n"
        f"{THEN_SENTINEL}\n"
        "```\n\n"
        f"{RATIONALE_SENTINEL}\n"
        f"{EXPECTED_SENTINEL}\n",
        encoding="utf-8",
    )


def _make_backend(log_path: Path):
    def backend(prompt, model, **params):
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

    return backend


def _read_log(log_path: Path):
    if not log_path.exists():
        return []
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_retry_feedback_is_distinct_bare_rid_section_and_echoed(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_acceptance_decoy(repo_root)

    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    log_path = tmp_path / "model_calls.jsonl"
    backend = _make_backend(log_path)
    bundle = _make_bundle()
    assert bundle.hint_code is None  # cold mode

    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        retry_feedback=["R-FOO-003"],
        repo_root=repo_root,
        llm_backend=backend,
    )

    # The mock model was actually called, once.
    calls = _read_log(log_path)
    assert len(calls) == 1, f"expected exactly one model call, got {len(calls)}"
    prompt = calls[0]["prompt"]
    assert isinstance(prompt, str) and prompt

    # The retry_feedback section, as generate itself renders it.
    sections_with = generator.render_prompt_sections(bundle, ["R-FOO-003"])
    sections_without = generator.render_prompt_sections(bundle, None)
    assert len(sections_with) == len(sections_without) + 1
    fb_title, fb_text = sections_with[-1]
    other_titles = [t for t, _ in sections_without]
    other_titles_with = [t for t, _ in sections_with[:-1]]
    assert other_titles_with == other_titles

    # Distinctly labeled: its own title, unlike every bundle-derived section.
    assert fb_title and fb_title.strip()
    assert fb_title not in other_titles
    assert fb_title in prompt

    # Contains only the R-id "R-FOO-003".
    assert "R-FOO-003" in fb_text
    assert set(R_ID_RE.findall(fb_text)) == {"R-FOO-003"}
    assert "MUST return" not in fb_text
    for s in SENTINELS:
        assert s not in fb_text

    # Not merged into any bundle-derived section.
    for _, text in sections_with[:-1]:
        assert "R-FOO-003" not in text

    # The section reaches the model verbatim, and R-FOO-003 appears in the
    # prompt only within that section.
    assert fb_text.strip() in prompt
    assert "R-FOO-003" in prompt
    remainder = prompt.replace(fb_text.strip(), "")
    assert "R-FOO-003" not in remainder

    # No Gherkin text, rationale, or expected/actual values anywhere.
    for s in SENTINELS:
        assert s not in prompt, f"acceptance content leaked into prompt: {s!r}"
    assert "```gherkin" not in prompt

    # The result echoes retry_feedback.
    assert field(result, "retry_feedback") == ["R-FOO-003"]
    assert field(result, "model_call_error") is None
    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False
    assert field(result, "files")