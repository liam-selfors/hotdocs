# hotdocs-criterion: sha256:f5e04eb5c26b9c20fabb6de5037beb8fb9910f1363156f8b634e12d5595f8950
import re
import uuid

import generator


USAGE_TEXT = (
    "Module: bar_usage_mod\n"
    "\n"
    "def compute_bar_usage_zq(value: int) -> int\n"
    "    Return the bar of value (USAGE_ONLY_MARKER_7731)."
)

INTERFACE_TEXT = (
    "# Library\n"
    "\n"
    "```\n"
    "bar_iface_zq(x: int) -> int\n"
    "```\n"
    "\n"
    "INTERFACE_ONLY_MARKER_4419"
)


class Bundle(dict):
    """A SpecBundle-shaped mapping that also allows attribute access."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def section(prompt, heading):
    lines = prompt.split("\n")
    start = lines.index(heading) + 1
    end = next((i for i in range(start, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]).rstrip("\n")


def make_bundle():
    return Bundle(
        component_id="comp-foo",
        spec_bundle_hash="sha256:" + uuid.uuid4().hex + uuid.uuid4().hex,
        spec="# Foo\n\n## Purpose\n\nFoo doubles a number using bar.\n\n# R-FOO-001\n\n**R-FOO-001** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={"comp-bar": INTERFACE_TEXT},
        dependency_context={"comp-bar": "Bar computes the bar of a number."},
        dependency_usage={"comp-bar": USAGE_TEXT},
        vars={},
        glossary="# Glossary\n\n- **Foo** — a test term.",
        hint_code=None,
    )


def test_dependency_usage_is_its_own_labeled_section(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    log_path = tmp_path / "mock_calls.log"
    prompt_path = tmp_path / "mock_prompt.txt"

    def mock_backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("call\n")
        with open(prompt_path, "w", encoding="utf-8") as fh:
            fh.write(prompt)
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

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    bundle = make_bundle()
    result = generator.generate(
        bundle,
        "claude-sonnet-5",
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    # The mock model was actually called (no refusal, no cache hit).
    assert log_path.is_file(), "mock model was never called"
    assert log_path.read_text(encoding="utf-8").count("call") >= 1
    assert field(result, "refused") is None
    assert field(result, "cache_hit") is False

    prompt = prompt_path.read_text(encoding="utf-8")
    lines = prompt.split("\n")

    # Both sections exist, each under its own distinct heading.
    assert "## DEPENDENCY USAGE" in lines
    assert "## DEPENDENCY INTERFACES" in lines
    assert lines.index("## DEPENDENCY USAGE") != lines.index("## DEPENDENCY INTERFACES")

    usage_section = section(prompt, "## DEPENDENCY USAGE")
    iface_section = section(prompt, "## DEPENDENCY INTERFACES")

    # dependency_usage appears in its own section, keyed by dependency.
    assert "### comp-bar" in usage_section.split("\n")
    assert USAGE_TEXT in usage_section
    assert "USAGE_ONLY_MARKER_7731" in usage_section
    assert "compute_bar_usage_zq(value: int) -> int" in usage_section

    # dependency_interfaces stays in its own section.
    assert "INTERFACE_ONLY_MARKER_4419" in iface_section

    # Never merged: neither section carries the other's content.
    assert "USAGE_ONLY_MARKER_7731" not in iface_section
    assert "compute_bar_usage_zq" not in iface_section
    assert "INTERFACE_ONLY_MARKER_4419" not in usage_section
    assert "bar_iface_zq" not in usage_section