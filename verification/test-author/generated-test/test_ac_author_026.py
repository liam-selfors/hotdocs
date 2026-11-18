# hotdocs-criterion: sha256:a9c2a275e7e101030337c16d3949e23ad1e8cc3893bfc2dc12ee5f0e5ca27615
import re

import test_author


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _make_bundle(component_id, criterion_id, covers, module_names):
    return _Bundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=(
            "Given a string\n"
            "When it is processed\n"
            "Then a result is returned"
        ),
        requirement_text="**" + covers + "** - processing MUST return a result.",
        interface="# Library\n\n```\nprocess(s: str) -> str\n```\n",
        glossary="# Glossary\n\n- **Foo** - a test term.\n",
        dependency_interfaces={},
        module_names=module_names,
    )


_NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def _make_backend(prompts):
    def backend(prompt, model, **params):
        prompts.append(prompt)
        match = _NONCE_RE.search(prompt)
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

    return backend


def _capture_prompts(bundle, repo_root):
    prompts = []
    backend = _make_backend(prompts)
    error = None
    try:
        test_author.author_test(
            bundle,
            "mock-model",
            0,
            repo_root=repo_root,
            llm_backend=backend,
        )
    except Exception as exc:  # the criterion concerns the prompt only
        error = exc
    assert prompts, "author_test never called the model backend: " + repr(error)
    return prompts


def test_module_names_replace_derived_import(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    bundle = _make_bundle(
        "capabilities/P-SLUGS",
        "SC-SLUGS-001",
        "P-SLUGS",
        ["slugify", "url_tools"],
    )

    prompts = _capture_prompts(bundle, repo_root)
    prompt = prompts[0]

    assert "import slugify" in prompt
    assert "import url_tools" in prompt
    for p in prompts:
        assert "import capabilities" not in p


def test_empty_module_names_falls_back_to_derived_name(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    bundle = _make_bundle(
        "comp-semver",
        "AC-SEMVER-001",
        "R-SEMVER-001",
        [],
    )

    prompts = _capture_prompts(bundle, repo_root)
    prompt = prompts[0]

    assert "import semver" in prompt