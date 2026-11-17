# hotdocs-criterion: sha256:b07824e481bba04a60d4ffcc1497f1a97f5940e06573603138df7ffbcbac5729
import re
import uuid

import generator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


class FakeBundle:
    """An object with the SpecBundle fields, readable by attribute or as a mapping."""

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

    def __init__(self, **kwargs):
        for name in self._FIELDS:
            setattr(self, name, kwargs[name])

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key not in self._FIELDS:
            return default
        return getattr(self, key)

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def __contains__(self, key):
        return key in self._FIELDS


GHERKIN_SENTINEL = "GHERKIN_SENTINEL_q7x81"
RATIONALE_SENTINEL = "RATIONALE_SENTINEL_m3k20"
EXPECTED_SENTINEL = "EXPECTED_SENTINEL_z9p44"
ACTUAL_SENTINEL = "ACTUAL_SENTINEL_w5n67"


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_fixture(repo_root):
    write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a test term.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
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
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "requirements" / "R-FOO-003.md",
        "# R-FOO-003\n\n**R-FOO-003** \u2014 `foo(0)` MUST return `0`.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: generated-test\n\n"
        "```gherkin\nGiven x = 2\nWhen foo(x) is called\nThen it returns 4\n```\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-003.md",
        "# AC-FOO-003\n\nCovers: R-FOO-003\nKind: generated-test\n\n"
        "```gherkin\n"
        "Given x = 0 and " + GHERKIN_SENTINEL + "\n"
        "When foo(x) is called\n"
        "Then it returns 0\n"
        "```\n\n"
        "Rationale: " + RATIONALE_SENTINEL + "\n"
        "Expected: " + EXPECTED_SENTINEL + "\n"
        "Actual: " + ACTUAL_SENTINEL + "\n",
    )
    write(comp / "interface" / "library.md", "# Library\n\n```\nfoo(x: int) -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")


def test_ac_gen_013_retry_feedback_is_separate_and_ids_only(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)

    spec_text = (
        "# Foo\n\n## Purpose\n\nFoo doubles a number.\n\n"
        "# R-FOO-001\n\n**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`."
    )
    bundle = FakeBundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + uuid.uuid4().hex + uuid.uuid4().hex,
        spec=spec_text,
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
        hint_code=None,
    )

    recorded = []

    def mock_backend(prompt, model, **params):
        recorded.append(prompt)
        nonces = re.findall(r"BEGIN FILE ([0-9a-f]{32})", prompt)
        if not nonces:
            nonces = re.findall(r"(?<![0-9a-f])([0-9a-f]{32})(?![0-9a-f])", prompt)
        blocks = []
        for nonce in dict.fromkeys(nonces):
            blocks.append(
                "-----BEGIN FILE " + nonce + ": foo.py-----\n"
                "def foo(x):\n"
                "    return 2 * x\n"
                "-----END FILE " + nonce + "-----\n"
            )
        return {
            "text": "Here you go.\n" + "".join(blocks),
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = generator.generate(
        bundle,
        "mock-model",
        ["R-FOO-003"],
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert len(recorded) == 1, "the mock model should have been called exactly once"
    prompt = recorded[0]
    assert isinstance(prompt, str)

    # retry_feedback appears as its own distinctly labeled section
    assert "## RETRY_FEEDBACK" in prompt.split("\n")
    fb = section(prompt, "## RETRY_FEEDBACK")
    non_empty = [line for line in fb.split("\n") if line.strip()]
    assert len(non_empty) == 2, fb
    assert non_empty[-1] == "- R-FOO-003"
    bullets = [line for line in non_empty if line.startswith("- ")]
    assert bullets == ["- R-FOO-003"]
    assert re.findall(r"R-[A-Z0-9]+-\d+", fb) == ["R-FOO-003"]

    # the R-id is not merged into any bundle field section
    assert prompt.count("R-FOO-003") == fb.count("R-FOO-003")
    for heading in ("## SPEC", "## INTERFACE", "## CONSTRAINTS", "## GLOSSARY"):
        assert "R-FOO-003" not in section(prompt, heading)

    # no acceptance-criterion content anywhere in the prompt
    for sentinel in (GHERKIN_SENTINEL, RATIONALE_SENTINEL, EXPECTED_SENTINEL, ACTUAL_SENTINEL):
        assert sentinel not in prompt
    assert "```gherkin" not in prompt
    assert "AC-FOO-003" not in prompt
    assert "AC-FOO-001" not in prompt
    assert "Then it returns 0" not in prompt
    assert "Then it returns 4" not in prompt

    # the result echoes retry_feedback
    assert list(field(result, "retry_feedback")) == ["R-FOO-003"]