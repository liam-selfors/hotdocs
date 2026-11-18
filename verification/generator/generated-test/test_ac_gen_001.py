# hotdocs-criterion: sha256:296ca67b813232de5b35276ac95c9d7957d6759f83c6ed98eccb12e43b394bf5
import re
from dataclasses import dataclass, field as dc_field, fields as dc_fields

import generator


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
        if key not in self.keys():
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self.keys():
            return getattr(self, key)
        return default

    def keys(self):
        return [f.name for f in dc_fields(self)]

    def __contains__(self, key):
        return key in self.keys()


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


def test_ac_gen_001_cold_prompt_built_from_bundle_sections(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)

    bundle = FakeSpecBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + "ac9e0010" * 8,
        spec="SPEC-MARK",
        interface="IFACE-MARK",
        constraints="CONS-MARK",
        dependency_interfaces={"comp-bar": "DI-MARK"},
        dependency_context={"comp-bar": "DC-MARK"},
        dependency_usage={"comp-bar": ""},
        vars={"VAR-X": "VAR-MARK"},
        glossary="GLOSS-MARK",
        hint_code=None,
    )

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
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

    generator.generate(
        bundle,
        "mock-model",
        repo_root=tmp_path,
        llm_backend=mock_backend,
    )

    assert len(recorded) == 1, "the mock model should have been called exactly once"
    prompt = recorded[0]

    assert section(prompt, "## SPEC") == "SPEC-MARK"
    assert section(prompt, "## DEPENDENCY CONTEXT") == "### comp-bar\nDC-MARK"

    expected_sections = {
        "## INTERFACE": "IFACE-MARK",
        "## CONSTRAINTS": "CONS-MARK",
        "## DEPENDENCY INTERFACES": "DI-MARK",
        "## VARS": "VAR-MARK",
        "## GLOSSARY": "GLOSS-MARK",
    }
    all_sections = dict(expected_sections)
    all_sections["## SPEC"] = "SPEC-MARK"
    all_sections["## DEPENDENCY CONTEXT"] = "DC-MARK"

    for heading, marker in expected_sections.items():
        text = section(prompt, heading)
        assert marker in text, heading + " should contain " + marker
    for heading, marker in all_sections.items():
        for other_heading in all_sections:
            if other_heading == heading:
                continue
            assert marker not in section(prompt, other_heading), (
                marker + " should only be in " + heading + ", found in " + other_heading
            )

    assert "### VAR-X" in section(prompt, "## VARS")
    assert "### comp-bar" in section(prompt, "## DEPENDENCY INTERFACES")

    prompt_lines = prompt.split("\n")
    assert "## DEPENDENCY USAGE" not in prompt_lines
    assert "## HINT_CODE" not in prompt_lines
    assert "## RETRY_FEEDBACK" not in prompt_lines