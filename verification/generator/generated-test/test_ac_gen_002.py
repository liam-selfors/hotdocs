# hotdocs-criterion: sha256:9d98968e486d52fecbdf4e7da39c0f35c12201434f9a0d193a21e3413e64f9b1
import json
import re
from pathlib import Path

import pytest

import generator


SPEC_TEXT = "Foo doubles a number. SPECTEXT_c0ld_9a1."
INTERFACE_TEXT = "foo(x: int) -> int  IFACETEXT_c0ld_2b7"
CONSTRAINTS_TEXT = "None. CONSTRAINTTEXT_c0ld_5e3"
GLOSSARY_TEXT = "- **Foo** — a test term. GLOSSTEXT_c0ld_8d4"
HINT_MARKER = "HINTMARKER_existing_code_7f3a"
HINT_CONTENT = "def foo(x):\n    # " + HINT_MARKER + "\n    return 2 * x\n"

COLD_HEADINGS = [
    "## SPEC",
    "## INTERFACE",
    "## CONSTRAINTS",
    "## DEPENDENCY INTERFACES",
    "## DEPENDENCY CONTEXT",
    "## VARS",
    "## GLOSSARY",
]


class Bundle(dict):
    """A SpecBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next(
        (i for i in range(start, len(lines)) if lines[i].startswith("## ")),
        len(lines),
    )
    return "\n".join(lines[start:end]).rstrip("\n")


def make_hint_bundle():
    return Bundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec=SPEC_TEXT,
        interface=INTERFACE_TEXT,
        constraints=CONSTRAINTS_TEXT,
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary=GLOSSARY_TEXT,
        hint_code={"foo.py": HINT_CONTENT},
    )


def make_recording_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt)
        nonce = m.group(1) if m else "0" * 32
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

    return backend


def test_hint_code_sent_as_distinct_labeled_section(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "model_calls.jsonl"

    bundle = make_hint_bundle()
    generator.generate(
        bundle,
        "anthropic:mock-model",
        repo_root=repo_root,
        llm_backend=make_recording_backend(log_path),
    )

    assert log_path.is_file(), "mock model was never called"
    records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) == 1
    prompt = records[0]["prompt"]
    lines = prompt.split("\n")

    # hint_code appears under its own distinctly labeled heading
    assert "## HINT_CODE" in lines
    hint_section = section(prompt, "## HINT_CODE")
    assert "--- hint file: foo.py ---" in hint_section
    assert "--- end hint file: foo.py ---" in hint_section
    assert HINT_MARKER in hint_section
    assert "return 2 * x" in hint_section

    # the hint code appears only in the HINT_CODE section, never merged elsewhere
    assert prompt.count(HINT_MARKER) == 1

    # every cold field section is present, separate, and free of hint code
    for heading in COLD_HEADINGS:
        assert heading in lines, heading
        text = section(prompt, heading)
        assert HINT_MARKER not in text, heading
        assert "--- hint file:" not in text, heading

    # cold fields live in their own sections, not inside the hint section
    assert SPEC_TEXT in section(prompt, "## SPEC")
    assert INTERFACE_TEXT in section(prompt, "## INTERFACE")
    assert CONSTRAINTS_TEXT in section(prompt, "## CONSTRAINTS")
    assert GLOSSARY_TEXT in section(prompt, "## GLOSSARY")
    for cold_text in (SPEC_TEXT, INTERFACE_TEXT, CONSTRAINTS_TEXT, GLOSSARY_TEXT):
        assert cold_text not in hint_section

    # the hint section is a different section from every cold one
    hint_idx = lines.index("## HINT_CODE")
    for heading in COLD_HEADINGS:
        assert lines.index(heading) != hint_idx