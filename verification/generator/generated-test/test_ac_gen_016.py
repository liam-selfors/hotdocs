# hotdocs-criterion: sha256:d80143ef89dfd898a8b2bad8a61c03c3de25c747f2018ee6a21041bba719402e
import re

import generator


COMPONENT_ID = "comp-widget-maker"
SLUG = "widget-maker"
MODULE = "widget_maker"


class Bundle(dict):
    """A SpecBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def make_bundle():
    return Bundle(
        component_id=COMPONENT_ID,
        spec_bundle_hash="sha256:" + "ab" * 32,
        spec="# Widgets\n\n## Purpose\n\nMakes widgets.\n\n**R-WIDGET-001** — `make(n)` MUST return n widgets.",
        interface="# Library\n\n```\nmake(n: int) -> list\n```",
        constraints="# Constraints\n\nNone.",
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary="# Glossary\n\n- **Widget** — a test term.",
        hint_code=None,
    )


def test_prompt_instructs_flat_module_or_package_directly_under_gen_component(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.chdir(tmp_path)

    calls = []

    def backend(prompt, model, **params):
        calls.append(prompt)
        nonce = re.search(r"-----BEGIN FILE ([0-9a-f]{32}):", prompt).group(1)
        text = (
            "-----BEGIN FILE " + nonce + ": " + MODULE + ".py-----\n"
            + "def make(n):\n    return [object() for _ in range(n)]\n"
            + "-----END FILE " + nonce + "-----\n"
            + "-----END REPLY " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    bundle = make_bundle()
    result = generator.generate(
        bundle, "claude-sonnet-5", repo_root=tmp_path, llm_backend=backend
    )

    assert len(calls) == 1, "the mock model should have been called exactly once"
    assert field(result, "cache_hit") is False
    prompt = calls[0]

    # The layout instruction is fixed scaffolding, so it appears in the
    # fixed instructions that precede every bundle-derived section.
    lines = prompt.split("\n")
    assert "## SPEC" in lines
    scaffolding = "\n".join(lines[: lines.index("## SPEC")])

    # Sanity: the bundle content itself never names these, so they come
    # from the scaffolding, not the bundle.
    for value in bundle.values():
        if isinstance(value, str):
            assert MODULE not in value
            assert "gen/" not in value

    # Names the real flat module and the real package for this component.
    assert MODULE + ".py" in scaffolding
    assert MODULE + "/" in scaffolding
    assert "__init__.py" in scaffolding

    # Directly under gen/<component>/ (the slug, never the comp- id).
    assert "gen/" + SLUG + "/" in scaffolding or "gen/" + SLUG in scaffolding

    # Rules out a deeper layout such as a src/ subdirectory.
    lowered = scaffolding.lower()
    assert any(word in lowered for word in ("src", "deeper", "nested", "subdirector")), (
        "the prompt should forbid a deeper (e.g. src/) layout"
    )