# hotdocs-criterion: sha256:5c8f94b2b3aee7474449900b6730b014b5da25200869c4839fd0ee0e275f1ca4
import hashlib
import re
from dataclasses import dataclass, field as dc_field

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


@dataclass
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

    def __getitem__(self, key):
        return getattr(self, key)

    def get(self, key, default=None):
        return getattr(self, key, default)

    def keys(self):
        return [
            "component_id", "spec_bundle_hash", "spec", "interface", "constraints",
            "dependency_interfaces", "dependency_context", "dependency_usage",
            "vars", "glossary", "hint_code",
        ]


# Acceptance-criterion content that must never reach the model.
GHERKIN_GIVEN = "Given x = 7331 for the hidden criterion"
GHERKIN_WHEN = "When foo(x) is called under the hidden criterion"
GHERKIN_THEN = "Then it returns 14662 per the hidden criterion"
RATIONALE_SENTINEL = "RATIONALE-SENTINEL-c0ffee"
EXPECTED_SENTINEL = "EXPECTED-SENTINEL-14662"
ACTUAL_SENTINEL = "ACTUAL-SENTINEL-99999"


def test_ac_gen_013_retry_feedback_is_bare_ids_in_own_section(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    digest = hashlib.sha256(("ac-gen-013-" + str(tmp_path)).encode("utf-8")).hexdigest()
    bundle = FakeSpecBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + digest,
        spec=(
            "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
            "# R-FOO-003\n\n**R-FOO-003** \u2014 `foo(x)` MUST return `2 * x`."
        ),
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
        hint_code=None,
    )

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            "def foo(x):\n"
            "    return 2 * x\n"
            "-----END FILE " + nonce + "-----\n"
            "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        ["R-FOO-003"],
        repo_root=tmp_path,
        llm_backend=mock_backend,
    )

    assert len(recorded) == 1, "the mock model should have been called exactly once"
    prompt = recorded[0]

    # retry_feedback is its own distinctly labeled section.
    lines = prompt.split("\n")
    assert "## RETRY_FEEDBACK" in lines
    assert lines.count("## RETRY_FEEDBACK") == 1

    # It is not merged into any bundle-derived section.
    for heading in ("## SPEC", "## INTERFACE", "## CONSTRAINTS", "## GLOSSARY"):
        assert heading in lines
        assert "RETRY_FEEDBACK" not in section(prompt, heading)
        assert lines.index(heading) < lines.index("## RETRY_FEEDBACK")

    retry_text = section(prompt, "## RETRY_FEEDBACK")

    # Exactly one id line, the supplied id, and no other R-id in the section.
    id_lines = [ln for ln in retry_text.split("\n") if ln.startswith("- ")]
    assert id_lines == ["- R-FOO-003"]
    assert set(re.findall(r"\bR-[A-Z0-9]+-\d+\b", retry_text)) == {"R-FOO-003"}

    # No acceptance-criterion content anywhere in the prompt.
    for forbidden in (
        GHERKIN_GIVEN, GHERKIN_WHEN, GHERKIN_THEN,
        RATIONALE_SENTINEL, EXPECTED_SENTINEL, ACTUAL_SENTINEL,
        "AC-FOO-003", "Covers: R-FOO-003", "```gherkin",
    ):
        assert forbidden not in prompt
    for forbidden in ("Given", "When ", "Then ", "rationale", "expected", "actual"):
        assert forbidden.lower() not in retry_text.lower() or forbidden in ("When ",) and False, (
            "retry feedback section contains criterion-like content: " + repr(retry_text)
        )

    # The result echoes the caller's retry_feedback.
    assert field(result, "retry_feedback") == ["R-FOO-003"]