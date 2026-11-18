# hotdocs-criterion: sha256:9d98968e486d52fecbdf4e7da39c0f35c12201434f9a0d193a21e3413e64f9b1
import re
from pathlib import Path

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


SPEC_MARKER = "SPECMARKER_7f3a Foo doubles a number."
INTERFACE_MARKER = "INTERFACEMARKER_9b21 foo(x: int) -> int"
CONSTRAINTS_MARKER = "CONSTRAINTSMARKER_4c88 None."
GLOSSARY_MARKER = "GLOSSARYMARKER_e512 Foo is a test term."
HINT_MARKER = "HINTMARKER_d0c4"
HINT_CONTENT = "def foo(x):\n    # " + HINT_MARKER + "\n    return 2 * x\n"
HINT_PATH = "foo.py"


def _write_fixture(repo_root):
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "component.md").write_text(
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
        "Foo doubles a number.\n",
        encoding="utf-8",
    )
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** — a test term.\n", encoding="utf-8"
    )


def test_hint_code_is_a_distinct_labeled_section(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(repo_root)

    bundle = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + "ab12" * 16,
        "spec": SPEC_MARKER,
        "interface": INTERFACE_MARKER,
        "constraints": CONSTRAINTS_MARKER,
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": GLOSSARY_MARKER,
        "hint_code": {HINT_PATH: HINT_CONTENT},
    }

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        m = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt)
        nonce = m.group(1) if m else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + ": foo.py-----\n"
            "def foo(x):\n"
            "    return 2 * x\n"
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
        "claude-sonnet-5",
        None,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert recorded, "mock model was never called"
    prompt = recorded[-1]
    assert field(result, "refused") is None

    lines = prompt.split("\n")
    # The hint code is under its own labeled heading.
    assert "## HINT_CODE" in lines

    # Cold bundle fields are present under their own headings.
    for heading in ("## SPEC", "## INTERFACE", "## CONSTRAINTS", "## GLOSSARY"):
        assert heading in lines, heading

    hint_section = section(prompt, "## HINT_CODE")
    assert "--- hint file: " + HINT_PATH + " ---" in hint_section
    assert "--- end hint file: " + HINT_PATH + " ---" in hint_section
    assert HINT_MARKER in hint_section
    assert HINT_CONTENT.rstrip("\n") in hint_section

    # Cold fields are not merged into the hint section.
    for marker in (SPEC_MARKER, INTERFACE_MARKER, CONSTRAINTS_MARKER, GLOSSARY_MARKER):
        assert marker not in hint_section

    # Hint code is not merged into any cold-field section.
    cold = {
        "## SPEC": SPEC_MARKER,
        "## INTERFACE": INTERFACE_MARKER,
        "## CONSTRAINTS": CONSTRAINTS_MARKER,
        "## GLOSSARY": GLOSSARY_MARKER,
    }
    for heading, marker in cold.items():
        text = section(prompt, heading)
        assert marker in text, heading
        assert HINT_MARKER not in text, heading

    # The hint marker appears only within the HINT_CODE section.
    assert prompt.count(HINT_MARKER) == hint_section.count(HINT_MARKER)

    # The hint section comes after the cold sections.
    hint_idx = lines.index("## HINT_CODE")
    for heading in cold:
        assert lines.index(heading) < hint_idx