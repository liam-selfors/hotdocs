# hotdocs-criterion: sha256:3745d3a5f20e1eb2114570f43981eb024d57d6cfb253f1b8681bb6871db11e57
import re
from pathlib import Path

import test_author


ERD_GRAPH_INTERFACE = (
    "# Library\n"
    "\n"
    "```\n"
    "build_graph(manifest, *, plan=None, dbt_links=None) -> dict\n"
    "```\n"
)


class _Bundle(dict):
    """A CriterionBundle stand-in readable both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


def make_bundle():
    return _Bundle(
        component_id="comp-erd-viewer",
        criterion_id="AC-ERD-VIEWER-001",
        covers="R-ERD-VIEWER-001",
        criterion_text=(
            "Given a manifest\n"
            "When render(manifest) is called\n"
            "Then it returns a non-empty string\n"
        ),
        requirement_text=(
            "# R-ERD-VIEWER-001\n\n"
            "**R-ERD-VIEWER-001** — `render(manifest)` MUST return a non-empty string."
        ),
        interface="# Library\n\n```\nrender(manifest: dict) -> str\n```\n",
        glossary="# Glossary\n\n- **Foo** — a test term.\n",
        dependency_interfaces={"comp-erd-graph": ERD_GRAPH_INTERFACE},
        module_names=["erd_viewer"],
    )


_NONCE_RE = re.compile(r"-----BEGIN FILE ([0-9a-f]{32})-----")


def make_backend(content, calls):
    def backend(prompt, model, **params):
        calls.append(prompt)
        match = _NONCE_RE.search(prompt)
        assert match is not None, "no nonce found in prompt"
        n = match.group(1)
        text = "-----BEGIN FILE " + n + "-----\n" + content + "\n-----END FILE " + n + "-----"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def test_unused_top_level_helper_is_not_a_fake(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo_helper"
    repo_root.mkdir()

    content = (
        "import erd_viewer\n"
        "\n"
        "\n"
        "def build_graph():\n"
        "    return {}\n"
        "\n"
        "\n"
        "def test_helper_used_locally():\n"
        "    graph = build_graph()\n"
        "    assert graph == {}\n"
        "    assert isinstance(erd_viewer.render({\"nodes\": []}), str)"
    )
    calls = []
    result = test_author.author_test(
        make_bundle(),
        "claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=make_backend(content, calls),
    )

    assert calls, "mock backend was never called"
    assert field(result, "model_call_error") is None

    file_info = field(result, "file")
    assert file_info is not None
    returned = field(file_info, "content")
    assert body(returned) == content

    path = Path(field(file_info, "path"))
    if not path.is_absolute():
        path = repo_root / path
    assert path.is_file()
    assert body(path.read_text()) == content


def test_fake_module_source_with_wrong_arity_is_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo_fake"
    repo_root.mkdir()

    fake_source = "def build_graph():\n    return {}\n"
    content = (
        "import erd_viewer\n"
        "\n"
        "FAKE_SOURCE = " + repr(fake_source) + "\n"
        "\n"
        "\n"
        "def test_with_fake_dependency(tmp_path):\n"
        "    target = tmp_path / 'gen' / 'erd-graph' / 'erd_graph.py'\n"
        "    target.parent.mkdir(parents=True)\n"
        "    target.write_text(FAKE_SOURCE)\n"
        "    assert isinstance(erd_viewer.render({'nodes': []}), str)"
    )
    calls = []
    result = test_author.author_test(
        make_bundle(),
        "claude-sonnet-5",
        0,
        repo_root=repo_root,
        llm_backend=make_backend(content, calls),
    )

    assert calls, "mock backend was never called"
    err = field(result, "model_call_error")
    assert err is not None
    assert field(err, "category") == "fake_signature_mismatch"
    try:
        message = field(err, "message")
    except (KeyError, AttributeError):
        message = None
    named = (message is not None and "build_graph" in str(message)) or "build_graph" in str(err)
    assert named, "error does not name build_graph: " + repr(err)