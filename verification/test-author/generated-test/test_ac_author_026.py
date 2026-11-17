# hotdocs-criterion: sha256:a9c2a275e7e101030337c16d3949e23ad1e8cc3893bfc2dc12ee5f0e5ca27615
import re

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle(dict):
    """A CriterionBundle readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def make_bundle(component_id, criterion_id, covers, module_names):
    return Bundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=(
            "Given an input value\n"
            "When the operation is performed\n"
            "Then the expected output is produced"
        ),
        requirement_text="**" + covers + "** - The operation MUST produce the expected output.",
        interface="# Library\n\n```\noperate(x: str) -> str\n```",
        glossary="# Glossary\n\n- **Foo** - a test term.",
        dependency_interfaces={},
        module_names=list(module_names),
    )


def run_and_capture_prompt(bundle, repo_root):
    prompts = []

    def backend(prompt, model, **params):
        prompts.append(prompt)
        match = NONCE_RE.search(prompt)
        nonce = match.group(1) if match else "0" * 32
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            "def test_placeholder():\n"
            "    assert True\n"
            "-----END FILE " + nonce + "-----"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        bundle,
        "claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=backend,
    )
    assert field(result, "model_call_error") is None
    assert len(prompts) >= 1, "author_test never called the model backend"
    return prompts


def test_module_names_replace_derived_name_for_capability(tmp_path):
    bundle = make_bundle(
        "capabilities/P-SLUGS",
        "AC-SLUGS-001",
        "R-SLUGS-001",
        ["slugify", "url_tools"],
    )
    prompts = run_and_capture_prompt(bundle, tmp_path)
    for prompt in prompts:
        assert "import slugify" in prompt
        assert "import url_tools" in prompt
        assert "import capabilities" not in prompt


def test_empty_module_names_falls_back_to_derived_name(tmp_path):
    bundle = make_bundle(
        "comp-semver",
        "AC-SEMVER-001",
        "R-SEMVER-001",
        [],
    )
    prompts = run_and_capture_prompt(bundle, tmp_path)
    for prompt in prompts:
        assert "import semver" in prompt