"""AC-GEN-013 (covers R-GEN-012).

Given a cold-mode SpecBundle, retry_feedback=["R-FOO-003"], and a mock
model that records what it was sent, when generate is called, then the
mock model's recorded input contains retry_feedback as a distinctly
labeled section containing only "R-FOO-003" (no Gherkin text, rationale,
or expected/actual values anywhere in the prompt), and the resulting
GenerationResult's retry_feedback field echoes ["R-FOO-003"].
"""

import dataclasses
import difflib
import hashlib
import re
from pathlib import Path

import pytest

import generator


MODEL = "claude-sonnet-5"

FOO_CODE = "def foo(x):\n    return 2 * x\n"

GHERKIN_SENTINEL = "ZQXGHERKINSENTINEL7731"
RATIONALE_SENTINEL = "ZQXRATIONALESENTINEL4410"
EXPECTED_SENTINEL = "ZQXEXPECTEDSENTINEL9921"
ACTUAL_SENTINEL = "ZQXACTUALSENTINEL5502"

COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: false\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)

REQ_001 = "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n"
REQ_003 = "# R-FOO-003\n\n**R-FOO-003** \u2014 `foo(0)` MUST return `0`.\n"

AC_001 = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given x = 2\n"
    "When foo(x) is called\n"
    "Then it returns 4\n"
    "```\n"
)

AC_003 = (
    "# AC-FOO-003\n"
    "\n"
    "Covers: R-FOO-003\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    f"Given x = 0 {GHERKIN_SENTINEL}\n"
    "When foo(x) is called\n"
    f"Then it returns 0 {GHERKIN_SENTINEL}\n"
    "```\n"
)

INTERFACE_MD = "# Library\n\n```\nfoo(x: int) -> int\n```\n"
CONSTRAINTS_MD = "# Constraints\n\nNone.\n"
GLOSSARY_MD = "# Glossary\n\n- **Foo** \u2014 a test term.\n"

PRIOR_FAILURE_REPORT = (
    "{\n"
    '  "criterion_id": "AC-FOO-003",\n'
    '  "covers": "R-FOO-003",\n'
    f'  "rationale": "{RATIONALE_SENTINEL}",\n'
    f'  "expected": "{EXPECTED_SENTINEL}",\n'
    f'  "actual": "{ACTUAL_SENTINEL}"\n'
    "}\n"
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
    hint_code: object = None

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

    def __contains__(self, key):
        return key in self._names()

    def __iter__(self):
        return iter(self._names())

    def __len__(self):
        return len(self._names())


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_repo(repo: Path) -> Path:
    repo.mkdir(parents=True, exist_ok=True)
    _write(repo / "specs" / "glossary.md", GLOSSARY_MD)
    comp = repo / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQ_001)
    _write(comp / "requirements" / "R-FOO-003.md", REQ_003)
    _write(comp / "acceptance" / "AC-FOO-001.md", AC_001)
    _write(comp / "acceptance" / "AC-FOO-003.md", AC_003)
    _write(comp / "interface" / "library.md", INTERFACE_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    # Prior-attempt failure details that must never reach the model.
    _write(repo / "verification" / "foo" / "prior_failure.json", PRIOR_FAILURE_REPORT)
    return repo


def _make_bundle() -> FakeSpecBundle:
    body = (
        "# Foo\n\n## Purpose\n\nFoo doubles a number."
    )
    spec = "\n\n".join(
        [body.strip(), REQ_001.strip(), REQ_003.strip()]
    )
    digest = hashlib.sha256(
        (spec + INTERFACE_MD + CONSTRAINTS_MD + GLOSSARY_MD).encode("utf-8")
    ).hexdigest()
    return FakeSpecBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + digest,
        spec=spec,
        interface=INTERFACE_MD.strip(),
        constraints=CONSTRAINTS_MD.strip(),
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary=GLOSSARY_MD.strip(),
        hint_code=None,
    )


def _make_backend(record):
    def backend(prompt, model, **params):
        record.append(prompt)
        text_prompt = prompt if isinstance(prompt, str) else str(prompt)
        nonces = re.findall(r"BEGIN FILE\s+([0-9a-f]{32})", text_prompt)
        if not nonces:
            nonces = re.findall(
                r"(?<![0-9A-Fa-f])[0-9a-f]{32}(?![0-9A-Fa-f])", text_prompt
            )
        unique = []
        for n in nonces:
            if n not in unique:
                unique.append(n)
        blocks = []
        for n in unique:
            blocks.append(
                f"-----BEGIN FILE {n}: foo.py-----\n"
                f"{FOO_CODE}"
                f"-----END FILE {n}-----\n"
            )
        text = "".join(blocks) if blocks else "no nonce found in prompt"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _normalize(prompt: str) -> str:
    return re.sub(r"(?<![0-9A-Fa-f])[0-9a-f]{32}(?![0-9A-Fa-f])", "<NONCE>", prompt)


def _inserted_text(base: str, new: str) -> str:
    base_tokens = re.findall(r"\S+", base)
    new_tokens = re.findall(r"\S+", new)
    matcher = difflib.SequenceMatcher(None, base_tokens, new_tokens, autojunk=False)
    parts = []
    for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if tag in ("insert", "replace"):
            parts.append(" ".join(new_tokens[j1:j2]))
    return "\n".join(parts)


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)
    workdir = tmp_path / "cwd"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    return tmp_path


def test_retry_feedback_is_distinct_rid_only_section_and_echoed(isolated_env):
    tmp_path = isolated_env
    bundle = _make_bundle()

    # Call under test: retry_feedback supplied.
    repo_retry = _make_repo(tmp_path / "repo_retry")
    retry_record = []
    result = generator.generate(
        bundle,
        MODEL,
        retry_feedback=["R-FOO-003"],
        repo_root=repo_retry,
        llm_backend=_make_backend(retry_record),
    )

    assert retry_record, (
        "the mock model was never called; refused="
        f"{_field(result, 'refused')!r}, model_call_error="
        f"{_field(result, 'model_call_error')!r}"
    )
    retry_prompt = retry_record[0]
    assert isinstance(retry_prompt, str)

    # The result echoes retry_feedback exactly.
    echoed = _field(result, "retry_feedback")
    assert echoed is not None
    assert list(echoed) == ["R-FOO-003"]

    # The failed R-id reaches the model.
    assert "R-FOO-003" in retry_prompt

    # No acceptance-criterion content anywhere in the prompt.
    for sentinel in (
        GHERKIN_SENTINEL,
        RATIONALE_SENTINEL,
        EXPECTED_SENTINEL,
        ACTUAL_SENTINEL,
    ):
        assert sentinel not in retry_prompt, sentinel
    assert "```gherkin" not in retry_prompt
    assert "Covers: R-FOO-003" not in retry_prompt
    assert "Covers: R-FOO-001" not in retry_prompt
    assert "When foo(x) is called" not in retry_prompt
    assert "Then it returns" not in retry_prompt

    # Baseline: same bundle, no retry_feedback, to isolate the section the
    # retry_feedback added to the prompt.
    repo_base = _make_repo(tmp_path / "repo_base")
    base_record = []
    base_result = generator.generate(
        bundle,
        MODEL,
        retry_feedback=None,
        repo_root=repo_base,
        llm_backend=_make_backend(base_record),
    )
    assert base_record, (
        "the mock model was never called for the baseline; refused="
        f"{_field(base_result, 'refused')!r}, model_call_error="
        f"{_field(base_result, 'model_call_error')!r}"
    )
    base_prompt = base_record[0]
    assert isinstance(base_prompt, str)
    assert _field(base_result, "retry_feedback") is None

    added = _inserted_text(_normalize(base_prompt), _normalize(retry_prompt))

    # The added section carries the R-id ...
    assert "R-FOO-003" in added, added
    # ... and only that R-id ...
    assert set(re.findall(r"R-[A-Z]+-\d+", added)) == {"R-FOO-003"}, added
    # ... under its own label (text beyond the bare R-id) ...
    label_text = added.replace("R-FOO-003", "")
    assert re.search(r"[A-Za-z]{3,}", label_text), added
    # ... never merged with the bundle's own field content.
    for bundle_fragment in (
        "doubles a number",
        "MUST return",
        "foo(x: int) -> int",
        "a test term",
    ):
        assert bundle_fragment not in added, (bundle_fragment, added)
    # ... and carries no acceptance content either.
    for sentinel in (
        GHERKIN_SENTINEL,
        RATIONALE_SENTINEL,
        EXPECTED_SENTINEL,
        ACTUAL_SENTINEL,
    ):
        assert sentinel not in added, sentinel