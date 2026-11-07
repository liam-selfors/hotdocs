import json
from pathlib import Path

import capability_scenario_verifier as csv


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


COMPONENT_MD_CACHE_MANAGER = """---
id: comp-cache-manager
title: Cache Manager
status: ratified
owners: [qa]
last_ratified_commit: 0000000
realizes: [P-ZERO-EDIT]
sealed: false
---

A cache manager component that realizes P-ZERO-EDIT.
"""

COMPONENT_MD_OTHER = """---
id: comp-other
title: Other
status: ratified
owners: [qa]
last_ratified_commit: 0000000
realizes: []
sealed: false
---

A component that realizes nothing.
"""

PRODUCT_MD = """---
id: P-ZERO-EDIT
title: Zero Edit
status: ratified
owners: [qa]
last_ratified_commit: 0000000
---

### CS-ZERO-EDIT-001

Covers: P-ZERO-EDIT
Kind: generated-test

```gherkin
Given a thing
When nothing changes
Then it stays the same
```
"""

TEST_AUTHOR_MODULE_TEMPLATE = '''
from pathlib import Path

CALLS_LOG = Path(r"{calls_log}")


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    with open(CALLS_LOG, "a", encoding="utf-8") as f:
        f.write(bundle["criterion_id"] + "\\n")
    slug = bundle["criterion_id"].lower().replace("-", "_")
    return {{
        "model_call_error": None,
        "file": {{
            "path": "verification/capabilities/P-ZERO-EDIT/generated-test/test_" + slug + ".py",
            "content": "def test_x():\\n    assert True\\n",
        }},
    }}
'''

LLM_ENDPOINT_MODULE = """
def complete(prompt, model, *, backend=None, **params):
    return {"text": "ok", "model": model, "backend": "fake", "model_call_error": None}
"""


def _build_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path / "repo"
    calls_log = repo_root / "_test_author_calls.log"

    _write(repo_root / "specs" / "product" / "zero-edit.md", PRODUCT_MD)
    _write(
        repo_root / "specs" / "components" / "cache-manager" / "component.md",
        COMPONENT_MD_CACHE_MANAGER,
    )
    _write(
        repo_root / "specs" / "components" / "other" / "component.md",
        COMPONENT_MD_OTHER,
    )
    _write(repo_root / "gen" / "cache-manager" / "cache_manager.py", "def noop():\n    return 1\n")
    _write(repo_root / "gen" / "other" / "other.py", "def noop():\n    return 2\n")
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        TEST_AUTHOR_MODULE_TEMPLATE.format(calls_log=str(calls_log)),
    )
    _write(repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py", LLM_ENDPOINT_MODULE)

    return repo_root


def _call_count(repo_root: Path) -> int:
    log = repo_root / "_test_author_calls.log"
    if not log.exists():
        return 0
    return len([line for line in log.read_text(encoding="utf-8").splitlines() if line])


def _read_provenance(repo_root: Path) -> dict:
    path = repo_root / "verification" / "capabilities" / "P-ZERO-EDIT" / ".provenance.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_provenance_hash_tracks_realizing_code_and_own_spec_but_not_others(tmp_path):
    repo_root = _build_repo(tmp_path)

    first_result = csv.run_capability_gates(
        "P-ZERO-EDIT", repo_root, model="anthropic:claude-sonnet-5", seed=0, llm_backend=None
    )
    assert _get(first_result, "hit") is False

    baseline_check = csv.check_capability_provenance("P-ZERO-EDIT", repo_root)
    assert _get(baseline_check, "hit") is True

    baseline_record = _read_provenance(repo_root)
    baseline_hash = baseline_record["content_hash"]
    calls_after_first_run = _call_count(repo_root)
    assert calls_after_first_run >= 1

    # 1. One byte changed under a realizing component's code directory, no spec touched.
    code_file = repo_root / "gen" / "cache-manager" / "cache_manager.py"
    original_code = code_file.read_text(encoding="utf-8")
    code_file.write_text(original_code + "#", encoding="utf-8")

    check_after_code_change = csv.check_capability_provenance("P-ZERO-EDIT", repo_root)
    assert _get(check_after_code_change, "hit") is False

    code_file.write_text(original_code, encoding="utf-8")
    assert _get(csv.check_capability_provenance("P-ZERO-EDIT", repo_root), "hit") is True

    # 2. The capability's own specs/product file changes.
    product_file = repo_root / "specs" / "product" / "zero-edit.md"
    original_product = product_file.read_text(encoding="utf-8")
    product_file.write_text(original_product + "\n<!-- edited -->\n", encoding="utf-8")

    check_after_spec_change = csv.check_capability_provenance("P-ZERO-EDIT", repo_root)
    assert _get(check_after_spec_change, "hit") is False

    product_file.write_text(original_product, encoding="utf-8")
    assert _get(csv.check_capability_provenance("P-ZERO-EDIT", repo_root), "hit") is True

    # 3a. A file in a non-realizing component changes: no effect.
    other_file = repo_root / "gen" / "other" / "other.py"
    other_file.write_text(other_file.read_text(encoding="utf-8") + "#", encoding="utf-8")
    assert _get(csv.check_capability_provenance("P-ZERO-EDIT", repo_root), "hit") is True

    # 3b. A __pycache__ file appears in a realizing component's code directory: no effect.
    pycache_file = repo_root / "gen" / "cache-manager" / "__pycache__" / "cache_manager.cpython-311.pyc"
    _write(pycache_file, "not real bytecode")
    assert _get(csv.check_capability_provenance("P-ZERO-EDIT", repo_root), "hit") is True

    # 4. Re-apply the first change and run the gates: scenarios re-run, hash changes.
    code_file.write_text(original_code + "#", encoding="utf-8")

    second_result = csv.run_capability_gates(
        "P-ZERO-EDIT", repo_root, model="anthropic:claude-sonnet-5", seed=0, llm_backend=None
    )
    assert _get(second_result, "hit") is False

    calls_after_second_run = _call_count(repo_root)
    assert calls_after_second_run > calls_after_first_run

    second_record = _read_provenance(repo_root)
    assert second_record["content_hash"] != baseline_hash