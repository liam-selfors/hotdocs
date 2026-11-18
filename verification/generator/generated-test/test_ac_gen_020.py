# hotdocs-criterion: sha256:2f0bbc4ea468170252d2f5646d87543dbc134ea76e657c330fc24b410fadcbee
import re

import pytest

import generator


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

COMPONENT_MD_WITH_DEP = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "sealed: false\n"
    "depends_on: [comp-bar]\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write_fixture(repo_root, component_md):
    comp_dir = repo_root / "specs" / "components" / "foo"
    comp_dir.mkdir(parents=True, exist_ok=True)
    (comp_dir / "component.md").write_text(component_md, encoding="utf-8")
    (repo_root / "specs" / "glossary.md").write_text(
        "# Glossary\n\n- **Foo** - a test term.\n", encoding="utf-8"
    )


def _bundle(with_dependency):
    bundle = {
        "component_id": "comp-foo",
        "spec_bundle_hash": "sha256:" + ("ab" * 32),
        "spec": "# Foo\n\nFoo doubles a number.\n\n# R-FOO-001\n\n**R-FOO-001** - `foo(x)` MUST return `2 * x`.",
        "interface": "# Library\n\n```\nfoo(x: int) -> int\n```",
        "constraints": "# Constraints\n\nNone.",
        "dependency_interfaces": {},
        "dependency_context": {},
        "dependency_usage": {},
        "vars": {},
        "glossary": "# Glossary\n\n- **Foo** - a test term.",
        "hint_code": None,
    }
    if with_dependency:
        bundle["dependency_interfaces"] = {
            "comp-bar": "# Library\n\n```\nbar(x: int) -> int\n```"
        }
        bundle["dependency_context"] = {"comp-bar": "Bar computes a number."}
        bundle["dependency_usage"] = {"comp-bar": ""}
    return bundle


def _find_nonce(prompt):
    m = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt)
    if m:
        return m.group(1)
    candidates = re.findall(r"(?<![0-9a-fA-F])([0-9a-f]{32})(?![0-9a-fA-F])", prompt)
    assert candidates, "prompt does not state a per-call nonce"
    return candidates[0]


def _make_backend(recorded):
    def backend(prompt, model, **params):
        recorded.append(prompt)
        nonce = _find_nonce(prompt)
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

    return backend


def _fixed_instructions(prompt):
    lines = prompt.split("\n")
    assert "## SPEC" in lines, "prompt has no '## SPEC' section heading"
    return "\n".join(lines[: lines.index("## SPEC")])


def _assert_dual_access_instruction(prompt):
    text = _fixed_instructions(prompt).lower()
    flat = re.sub(r"\s+", " ", text)

    assert "dependenc" in flat, "fixed instructions never mention dependencies"
    assert "dict" in flat, "fixed instructions never mention dict access"
    assert "attribute" in flat or "getattr" in flat, (
        "fixed instructions never mention attribute access"
    )
    # The instruction must cover the dependency's own top-level return value,
    # not only nested values.
    assert (
        "top-level" in flat
        or "top level" in flat
        or "return value" in flat
        or "returned value" in flat
        or "value it returns" in flat
        or "itself returns" in flat
    ), "fixed instructions do not cover the dependency's own top-level return value"
    # It must forbid bare attribute access alone.
    assert (
        "never" in flat or "not " in flat or "must not" in flat
    ), "fixed instructions do not forbid bare attribute access"
    assert (
        "bare" in flat or "alone" in flat or "only" in flat or ".attr" in flat
    ), "fixed instructions do not rule out a bare attribute access alone"


@pytest.mark.parametrize("with_dependency", [False, True])
def test_prompt_instructs_dual_access_for_dependency_values(
    tmp_path, monkeypatch, with_dependency
):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_fixture(
        repo_root, COMPONENT_MD_WITH_DEP if with_dependency else COMPONENT_MD
    )

    recorded = []
    result = generator.generate(
        _bundle(with_dependency),
        "mock-model",
        repo_root=repo_root,
        llm_backend=_make_backend(recorded),
    )

    assert field(result, "refused") is None
    assert len(recorded) >= 1, "mock model was never called"
    for prompt in recorded:
        _assert_dual_access_instruction(prompt)