import dataclasses
import importlib.util
import json
import re
import sys
import uuid
from pathlib import Path

import pytest

import test_author


ALLOWED_BUNDLE_FIELDS = {
    "component_id",
    "criterion_id",
    "covers",
    "criterion_text",
    "requirement_text",
    "interface",
    "glossary",
    "dependency_interfaces",
    "module_names",
}


def _get(value, key):
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)


def _find_gen_dir():
    candidates = []
    try:
        candidates.extend(Path(test_author.__file__).resolve().parents)
    except Exception:
        pass
    for p in candidates:
        if p.name == "gen":
            return p
    for p in Path(__file__).resolve().parents:
        g = p / "gen"
        if (g / "spec-bundle-assembler").is_dir():
            return g
    return None


def _load_from_gen(gen, slug, module_name):
    base = gen / slug
    flat = base / f"{module_name}.py"
    path = flat if flat.is_file() else base / module_name / "__init__.py"
    if not path.is_file():
        pytest.fail(f"cannot locate {module_name} under {base}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module  # register BEFORE exec_module
    spec.loader.exec_module(module)
    return module


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [team-a]
sealed: true
source_path: legacy/foo/
depends_on: []
---

# Foo

## Purpose

Foo doubles a number.
"""

GLOSSARY_MD = """# Glossary

- **Foo** — a test term.
"""

REQUIREMENT_MD = """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`.
"""

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""

INTERFACE_MD = """# Library

```
foo(x: int) -> int
```
"""

CONSTRAINTS_MD = """# Constraints

None.
"""


def _build_corpus(repo_root, marker):
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    _write(comp / "interface" / "library.md", INTERFACE_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(
        repo_root / "legacy" / "foo" / "foo.py",
        "def foo(x):\n    return 2 * x\n",
    )
    # Existing gen/<component>/ content, each file carrying a unique marker.
    _write(
        repo_root / "gen" / "foo" / "foo.py",
        f"# {marker}\n"
        f"def foo(x):\n"
        f"    return x + x  # {marker}\n"
        f"\n"
        f"def {marker.lower()}_helper():\n"
        f"    return '{marker}'\n",
    )
    _write(
        repo_root / "gen" / "foo" / "notes.txt",
        f"implementation detail {marker}\n",
    )


def _bundle_items(bundle):
    if isinstance(bundle, dict):
        return dict(bundle)
    if dataclasses.is_dataclass(bundle):
        return {f.name: getattr(bundle, f.name) for f in dataclasses.fields(bundle)}
    if hasattr(bundle, "keys"):
        return {k: bundle[k] for k in bundle.keys()}
    return dict(vars(bundle))


def _all_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _all_strings(k)
            yield from _all_strings(v)
    elif isinstance(value, (list, tuple, set)):
        for v in value:
            yield from _all_strings(v)
    elif value is None or isinstance(value, (int, float, bool)):
        return
    else:
        yield str(value)


def test_ac_author_002_bundle_contains_no_gen_content(tmp_path, monkeypatch):
    marker = "GENMARKER" + uuid.uuid4().hex.upper()
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root, marker)

    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.delenv("VAR_CACHE_STORE_URL", raising=False)
    monkeypatch.delenv("VAR_HOTDOCS_CONFIG", raising=False)

    gen = _find_gen_dir()
    assert gen is not None, "could not locate the tool's gen/ directory"

    spec_linter = _load_from_gen(gen, "spec-linter", "spec_linter")
    lint_result = spec_linter.lint(None, repo_root)
    hard = _get(lint_result, "hard_failures")
    assert hard == 0, f"fixture is not lint-clean: {lint_result!r}"

    assembler = _load_from_gen(gen, "spec-bundle-assembler", "spec_bundle_assembler")
    bundle = assembler.assemble_criterion("comp-foo", "AC-FOO-001", repo_root)

    items = _bundle_items(bundle)

    # Only the documented CriterionBundle fields — nothing like hint_code or files.
    extra = set(items) - ALLOWED_BUNDLE_FIELDS
    assert not extra, f"CriterionBundle carries undocumented fields: {sorted(extra)}"
    assert "hint_code" not in items

    # No field value (at any depth) is derived from gen/foo/ content.
    for name, value in items.items():
        for s in _all_strings(value):
            assert marker not in s, f"field {name!r} contains gen/<component>/ content"
            assert marker.lower() not in s, f"field {name!r} contains gen/<component>/ content"

    # Sanity: the bundle does carry the interface contract.
    interface_text = items.get("interface") or ""
    assert "foo(x: int) -> int" in interface_text

    # End-to-end: the component under test never adds gen/<component>/ content
    # to what it sends the model either.
    log_path = tmp_path / "backend_calls.jsonl"

    def backend(prompt, model, **params):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"prompt": prompt, "model": model}) + "\n")
        m = re.search(r"-----BEGIN FILE ([0-9a-f]+)-----", prompt)
        nonce = m.group(1) if m else ""
        body = "def test_placeholder():\n    assert True\n"
        text = f"-----BEGIN FILE {nonce}-----\n{body}-----END FILE {nonce}-----\n"
        return {
            "text": text,
            "model": model,
            "backend": "mock",
            "model_call_error": None,
        }

    result = test_author.author_test(
        bundle, "claude-sonnet-5", 0, repo_root=repo_root, llm_backend=backend
    )
    assert result is not None

    assert log_path.is_file(), "mock backend was never called"
    records = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert records, "mock backend was never called"
    for rec in records:
        prompt = rec["prompt"]
        assert marker not in prompt, "prompt contains gen/<component>/ content"
        assert marker.lower() not in prompt, "prompt contains gen/<component>/ content"
        assert "x + x" not in prompt, "prompt contains gen/<component>/ implementation"