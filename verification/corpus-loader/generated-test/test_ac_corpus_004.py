# hotdocs-criterion: sha256:86e2b8a38332a541223b65b64e2e521f3048f1df9945e786ad7bd4b6efba1ed7
import os
from pathlib import Path

import pytest

import corpus_loader


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [alice]
sealed: true
source_path: legacy/foo
---

# comp-foo

## Purpose

Foo exists to exercise the corpus loader in a synthetic fixture.
"""

REQUIREMENT_MD = """# R-FOO-001

**R-FOO-001** — `foo()` MUST return the integer 1.
"""

ACCEPTANCE_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given nothing
When foo() runs
Then it returns 1
```
"""

LIBRARY_MD = """# Library

```
foo() -> int
```

Returns 1.
"""

GUARANTEE_MD = """# G-FOO-001

`foo()` never raises.
"""

CONSTRAINTS_MD = """# Constraints

None.
"""

VAR_MD = """---
id: VAR-FOO
title: Foo variable
status: draft
owners: [alice]
---

# VAR-FOO

A synthetic variable.
"""

DECISION_MD = """---
id: D1
title: First decision
status: draft
owners: [alice]
---

# D1

A synthetic decision.
"""

PRODUCT_MD = """---
id: P-FOO
title: Foo product
status: draft
owners: [alice]
---

# P-FOO

A synthetic product capability.
"""

ARCHITECTURE_MD = """---
id: ARCH-FOO
title: Foo architecture
status: draft
owners: [alice]
---

# Foo architecture

A synthetic architecture note.
"""

GLOSSARY_MD = """# Glossary

- **Foo** — a synthetic term used by the fixture.
"""


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    specs = root / "specs"
    comp = specs / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    _write(comp / "interface" / "library.md", LIBRARY_MD)
    _write(comp / "interface" / "guarantees" / "G-FOO-001.md", GUARANTEE_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)
    _write(specs / "vars" / "VAR-FOO.md", VAR_MD)
    _write(specs / "decisions" / "D1.md", DECISION_MD)
    _write(specs / "product" / "P-FOO.md", PRODUCT_MD)
    _write(specs / "architecture" / "foo.md", ARCHITECTURE_MD)
    _write(specs / "glossary.md", GLOSSARY_MD)
    return root


def _iter_docs(corpus):
    docs = _get(corpus, "docs")
    assert docs is not None, "Corpus has no docs"
    if isinstance(docs, dict):
        return list(docs.values())
    return list(docs)


def _find_doc(corpus, rel_path):
    for doc in _iter_docs(corpus):
        if _get(doc, "rel_path") == rel_path:
            return doc
    return None


def test_ac_corpus_004(repo_root):
    assert not (repo_root / "gen").exists()

    corpus = corpus_loader.load_corpus(repo_root)

    req_rel = "specs/components/foo/requirements/R-FOO-001.md"
    req_path = repo_root / req_rel
    req_doc = _find_doc(corpus, req_rel)
    assert req_doc is not None, "requirement Doc not found by rel_path"

    assert _get(req_doc, "has_frontmatter") is False
    fm = _get(req_doc, "frontmatter")
    assert fm is not None
    assert dict(fm) == {}
    with open(req_path, "r", encoding="utf-8", newline="") as fh:
        whole_text = fh.read()
    assert _get(req_doc, "body") == whole_text

    comp_rel = "specs/components/foo/component.md"
    comp_doc = _find_doc(corpus, comp_rel)
    assert comp_doc is not None, "component.md Doc not found by rel_path"
    assert _get(comp_doc, "has_frontmatter") is True

    graph = _get(corpus, "graph")
    assert graph is not None, "Corpus has no graph connection"
    row = graph.execute("SELECT count(*) FROM nodes").fetchone()
    assert row is not None
    count = row[0]
    assert isinstance(count, int)
    assert count >= 1

    assert not (repo_root / "gen").exists()