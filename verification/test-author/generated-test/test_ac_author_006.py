import json
import os
import re
from pathlib import Path

import pytest

import test_author


def _get(value, key, default=None):
    if value is None:
        return default
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


class _Bundle:
    """A CriterionBundle stand-in readable both by attribute and as a mapping."""

    _FIELDS = (
        "component_id",
        "criterion_id",
        "covers",
        "criterion_text",
        "requirement_text",
        "interface",
        "glossary",
        "dependency_interfaces",
    )

    def __init__(self, **kwargs):
        self._data = dict(kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __getitem__(self, key):
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def __contains__(self, key):
        return key in self._data

    def keys(self):
        return self._data.keys()

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()

    def __iter__(self):
        return iter(self._data)

    def __len__(self):
        return len(self._data)


GLOSSARY = "# Glossary\n\n- **Foo** — a test term."


def _make_bundle(component_id, criterion_id, req_id, module_name):
    return _Bundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=req_id,
        criterion_text=(
            "Given x = 2\n"
            "When foo(x) is called\n"
            "Then it returns 4"
        ),
        requirement_text=(
            "# " + req_id + "\n\n**" + req_id + "** — `foo(x)` MUST return `2 * x`."
        ),
        interface="# Library\n\n```\nfoo(x: int) -> int\n```",
        glossary=GLOSSARY,
        dependency_interfaces={},
        module_names=[module_name],
    )


TEST_BODY = (
    "import foo\n"
    "\n"
    "\n"
    "def test_foo_doubles():\n"
    "    assert foo.foo(2) == 4\n"
)


def _make_backend(log_path):
    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"model": model}) + "\n")
        m = re.search(r"BEGIN FILE ([0-9a-f]{32})", prompt)
        if m is None:
            m = re.search(r"\b([0-9a-f]{32})\b", prompt)
        nonce = m.group(1) if m else ""
        text = (
            "-----BEGIN FILE " + nonce + "-----\n"
            + TEST_BODY
            + "-----END FILE " + nonce + "-----\n"
        )
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    return backend


def _list_files(root):
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file()]


@pytest.mark.parametrize(
    "component_id,slug,criterion_id,req_id,module_name,expected_name",
    [
        ("comp-foo", "foo", "AC-FOO-003", "R-FOO-003", "foo", "test_ac_foo_003.py"),
        (
            "comp-bar-baz",
            "bar-baz",
            "AC-BAR-BAZ-012",
            "R-BAR-BAZ-012",
            "bar_baz",
            "test_ac_bar_baz_012.py",
        ),
    ],
)
def test_output_written_only_under_generated_test_dir(
    tmp_path, monkeypatch, component_id, slug, criterion_id, req_id, module_name,
    expected_name,
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    log_path = log_dir / "backend_calls.jsonl"

    monkeypatch.chdir(repo_root)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    bundle = _make_bundle(component_id, criterion_id, req_id, module_name)

    result = test_author.author_test(
        bundle,
        "mock-model",
        0,
        repo_root=repo_root,
        llm_backend=_make_backend(log_path),
    )

    assert _get(result, "model_call_error") is None, _get(result, "model_call_error")
    file_info = _get(result, "file")
    assert file_info is not None

    reported_path = _get(file_info, "path")
    assert reported_path, "result.file.path must be populated"
    reported = Path(str(reported_path))
    if reported.is_absolute():
        rel = reported.resolve().relative_to(repo_root.resolve())
    else:
        rel = reported
    rel_posix = rel.as_posix()

    expected_rel = "verification/" + slug + "/generated-test/" + expected_name
    assert rel_posix == expected_rel, (rel_posix, expected_rel)

    # Never under gen/ and never under criterion-compiler's own output dir.
    parts = rel.parts
    assert parts[0] != "gen"
    assert "gen" not in parts
    assert "compiled" not in parts
    assert not rel_posix.startswith("gen/")
    assert not rel_posix.startswith("verification/" + slug + "/compiled/")

    # Filename is exactly the glossary formula, directly in the dir (no nesting/suffix).
    assert rel.name == expected_name
    assert rel.parent.as_posix() == "verification/" + slug + "/generated-test"

    # The file really exists on disk at exactly that location.
    on_disk = repo_root / "verification" / slug / "generated-test" / expected_name
    assert on_disk.is_file()
    content = _get(file_info, "content")
    if content is not None:
        assert on_disk.read_text(encoding="utf-8") == content

    # Nothing written under gen/ or under criterion-compiler's compiled/ dir.
    assert _list_files(repo_root / "gen") == []
    assert _list_files(repo_root / "verification" / slug / "compiled") == []

    # The only file inside verification/ is the one test file.
    verification_files = [
        p.resolve().relative_to(repo_root.resolve()).as_posix()
        for p in _list_files(repo_root / "verification")
    ]
    assert verification_files == [expected_rel], verification_files

    # No stray hashed/suffixed sibling in the generated-test directory.
    gen_test_dir = repo_root / "verification" / slug / "generated-test"
    siblings = sorted(p.name for p in gen_test_dir.iterdir())
    assert siblings == [expected_name], siblings