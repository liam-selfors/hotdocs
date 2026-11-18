# hotdocs-criterion: sha256:714985c25761bea5b6c2bf8930a725192e98462cc8142cc3524a4ae6adb2e7d5
import re
from pathlib import Path

import test_author


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


class Bundle(dict):
    """A CriterionBundle that reads both as a mapping and by attribute."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


TEST_BODY = "import foo\n\n\ndef test_foo():\n    assert foo.foo(2) == 4"


def make_backend(calls):
    def backend(prompt, model, **params):
        calls.append(model)
        m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
        assert m is not None, "prompt carries no BEGIN FILE nonce marker"
        n = m.group(1)
        text = "-----BEGIN FILE " + n + "-----\n" + TEST_BODY + "\n-----END FILE " + n + "-----"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def make_bundle():
    return Bundle(
        component_id="comp-foo",
        criterion_id="AC-FOO-003",
        covers="R-FOO-003",
        criterion_text="Given x = 2\nWhen foo(x) is called\nThen it returns 4",
        requirement_text="# R-FOO-003\n\n**R-FOO-003** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary="# Glossary\n\n- **Foo** — a test term.",
        dependency_interfaces={},
        module_names=["foo"],
    )


def test_output_written_under_verification_generated_test(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)

    calls = []
    result = test_author.author_test(
        make_bundle(),
        "mock:model-x",
        0,
        repo_root=repo_root,
        llm_backend=make_backend(calls),
    )

    assert field(result, "model_call_error") is None
    file_entry = field(result, "file")
    assert file_entry is not None
    raw_path = Path(field(file_entry, "path"))
    written = raw_path if raw_path.is_absolute() else repo_root / raw_path
    written = written.resolve()
    root = repo_root.resolve()

    expected_dir = (root / "verification" / "foo" / "generated-test").resolve()
    expected = expected_dir / "test_ac_foo_003.py"

    # Directly under verification/<component>/generated-test/, with the D63 filename.
    assert written.parent == expected_dir
    assert written.name == "test_ac_foo_003.py"
    assert written == expected
    assert expected.is_file()
    assert body(expected.read_text()) == TEST_BODY

    # Never under gen/<component>/ (or gen/ at all).
    rel_parts = written.relative_to(root).parts
    assert rel_parts[0] != "gen"
    gen_dir = root / "gen" / "foo"
    assert not gen_dir.exists() or not any(p.is_file() for p in gen_dir.rglob("*"))

    # Never in criterion-compiler's own output directory.
    compiled_dir = root / "verification" / "foo" / "compiled"
    assert compiled_dir not in written.parents
    assert not compiled_dir.exists() or not any(p.is_file() for p in compiled_dir.rglob("*"))

    # The relative path the result reports matches the same location.
    if not raw_path.is_absolute():
        assert raw_path.as_posix() == "verification/foo/generated-test/test_ac_foo_003.py"