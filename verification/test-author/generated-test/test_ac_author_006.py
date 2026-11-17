import re
from pathlib import Path

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


class _Bundle(dict):
    """A CriterionBundle that reads both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _make_bundle():
    return _Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-003",
        covers="R-FOO-003",
        criterion_text=(
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4"
        ),
        requirement_text="# R-FOO-003\n\n**R-FOO-003** \u2014 `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** \u2014 a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


EXTRACTED = "import foo\n\n\ndef test_foo():\n    assert foo.foo(2) == 4"


def _mock_backend(prompt, model, **params):
    m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
    assert m is not None, "prompt carries no BEGIN FILE nonce marker"
    n = m.group(1)
    text = (
        "-----BEGIN FILE " + n + "-----\n"
        + EXTRACTED
        + "\n-----END FILE " + n + "-----"
    )
    return {
        "text": text,
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def test_ac_author_006_output_written_only_under_generated_test(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    result = test_author.author_test(
        _make_bundle(),
        "mock:test-model",
        0,
        repo_root=repo_root,
        llm_backend=_mock_backend,
    )

    # A successful call.
    assert field(result, "model_call_error") is None
    file_entry = field(result, "file")
    assert file_entry is not None
    path_value = field(file_entry, "path")
    assert path_value

    path = Path(path_value)
    abs_path = path if path.is_absolute() else repo_root / path
    abs_path = abs_path.resolve()
    root = repo_root.resolve()

    # The written file exists and lives inside repo_root.
    assert abs_path.is_file(), "written file not found at " + str(abs_path)
    rel = abs_path.relative_to(root)

    # Then: under verification/<component>/generated-test/ (slug, not comp- id),
    # directly, with the glossary's criterion test filename.
    assert rel.parts == ("verification", "foo", "generated-test", "test_ac_foo_003.py"), rel.parts
    assert abs_path.parent == (root / "verification" / "foo" / "generated-test").resolve()

    # And not under gen/<component>/ nor criterion-compiler's own output directory.
    assert rel.parts[0] != "gen"
    gen_dir = (root / "gen").resolve()
    compiled_dir = (root / "verification" / "foo" / "compiled").resolve()
    assert gen_dir not in abs_path.parents
    assert compiled_dir not in abs_path.parents

    # Nothing at all was written under gen/ or criterion-compiler's directory.
    assert not gen_dir.exists() or not any(p.is_file() for p in gen_dir.rglob("*"))
    assert not compiled_dir.exists() or not any(p.is_file() for p in compiled_dir.rglob("*"))

    # The file at that path holds the authored test.
    written = abs_path.read_text()
    assert body(written) == EXTRACTED