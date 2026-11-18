# hotdocs-criterion: sha256:714985c25761bea5b6c2bf8930a725192e98462cc8142cc3524a4ae6adb2e7d5
import re
from pathlib import Path

import test_author


COMPONENT_ID = "comp-foo"
SLUG = "foo"
CRITERION_ID = "AC-FOO-003"
EXPECTED_REL = Path("verification") / SLUG / "generated-test" / "test_ac_foo_003.py"
BODY = "import foo\n\n\ndef test_doubles():\n    assert foo.foo(2) == 4\n"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def body(content):
    first, _, rest = content.partition("\n")
    return rest if first.startswith("# hotdocs-criterion:") else content


class Bundle:
    """A CriterionBundle stand-in readable both by attribute and as a mapping."""

    _fields = (
        "component_id",
        "criterion_id",
        "covers",
        "criterion_text",
        "requirement_text",
        "interface",
        "glossary",
        "dependency_interfaces",
        "module_names",
    )

    def __init__(self, **kwargs):
        for name in self._fields:
            setattr(self, name, kwargs.get(name))

    def __getitem__(self, key):
        if key not in self._fields:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self._fields:
            value = getattr(self, key)
            return default if value is None and default is not None else value
        return default

    def keys(self):
        return list(self._fields)

    def __iter__(self):
        return iter(self._fields)

    def __contains__(self, key):
        return key in self._fields

    def __len__(self):
        return len(self._fields)

    def items(self):
        return [(k, getattr(self, k)) for k in self._fields]

    def values(self):
        return [getattr(self, k) for k in self._fields]


def make_bundle():
    return Bundle(
        component_id=COMPONENT_ID,
        criterion_id=CRITERION_ID,
        covers="R-FOO-003",
        criterion_text=(
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4\n"
        ),
        requirement_text="**R-FOO-003** — `foo(x)` MUST return `2 * x`.",
        interface="# Library\n\n```\nfoo(x: int) -> int\n```\n",
        glossary="# Glossary\n\n- **Foo** — a test term.\n",
        dependency_interfaces={},
        module_names=["foo"],
    )


def mock_backend(prompt, model, **params):
    m = re.search(r"-----BEGIN FILE ([0-9a-f]{32})-----", prompt)
    assert m is not None, "prompt carries no BEGIN FILE nonce"
    n = m.group(1)
    text = "-----BEGIN FILE " + n + "-----\n" + BODY + "\n-----END FILE " + n + "-----"
    return {
        "text": text,
        "model": model,
        "backend": "mock",
        "model_call_error": None,
    }


def test_output_written_only_under_verification_generated_test(tmp_path, monkeypatch):
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    result = test_author.author_test(
        make_bundle(),
        "mock:model",
        0,
        repo_root=repo_root,
        llm_backend=mock_backend,
    )

    assert field(result, "model_call_error") is None
    file_entry = field(result, "file")
    assert file_entry is not None
    raw_path = Path(field(file_entry, "path"))

    # Resolve the reported path relative to repo_root.
    full_path = raw_path if raw_path.is_absolute() else repo_root / raw_path
    full_path = full_path.resolve()
    rel = full_path.relative_to(repo_root.resolve())

    # Exactly under verification/<slug>/generated-test/, with the D63 filename.
    assert rel == EXPECTED_REL, rel
    assert rel.parts[:3] == ("verification", SLUG, "generated-test")
    assert rel.parts[0] != "gen"
    assert "compiled" not in rel.parts

    # The file was actually written there, with the expected content.
    assert full_path.is_file()
    written = full_path.read_text()
    assert body(written) == BODY
    assert written == field(file_entry, "content")

    # Nothing was written under gen/<component>/ or criterion-compiler's output dir.
    gen_dir = repo_root / "gen" / SLUG
    assert not gen_dir.exists() or not any(p.is_file() for p in gen_dir.rglob("*"))
    compiled_dir = repo_root / "verification" / SLUG / "compiled"
    assert not compiled_dir.exists() or not any(p.is_file() for p in compiled_dir.rglob("*"))

    # The only copy of the test file in the repo is the expected one.
    found = [p.resolve() for p in repo_root.rglob("test_ac_foo_003.py")]
    assert found == [full_path]