import json
from pathlib import Path

import pytest

import provenance_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


ASSEMBLER_SRC = '''
import json
from dataclasses import dataclass, field as dc_field
from pathlib import Path

_LOG = Path(__file__).resolve().parent / "assemble_calls.jsonl"


@dataclass
class SpecBundle:
    component_id: str
    spec_bundle_hash: str
    spec: str
    interface: str
    constraints: str
    dependency_interfaces: dict = dc_field(default_factory=dict)
    dependency_context: dict = dc_field(default_factory=dict)
    dependency_usage: dict = dc_field(default_factory=dict)
    vars: dict = dc_field(default_factory=dict)
    glossary: str = ""
    hint_code: object = None

    def __getitem__(self, key):
        if key not in self.__dataclass_fields__:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def keys(self):
        return list(self.__dataclass_fields__)


def assemble(component_id, repo_root, mode="cold"):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "component_id": component_id,
            "repo_root": str(repo_root),
            "mode": mode,
        }) + "\\n")
    RAISE_MARKER
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:abc",
        spec="",
        interface="",
        constraints="",
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    raise NotImplementedError("not used by this test")
'''


COMPILER_SRC = '''
GATE_VERSION = "cc@1"


def compile(component_id, repo_root, target="pytest", out_dir=None):
    raise NotImplementedError("not used by this test")


def compile_criterion(criterion, surface=None):
    return {"status": "error", "message": "line 1: not used by this test"}
'''


TEST_AUTHOR_SRC = '''
GATE_VERSION = "ta@1"


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    raise NotImplementedError("not used by this test")
'''


VERIFIER_SRC = '''
GATE_VERSION = "vo@1"


def verify(component_id, repo_root, judge=None, test_author=None):
    raise NotImplementedError("not used by this test")
'''


LICENSE_SRC = '''
import json
from pathlib import Path

_LOG = Path(__file__).resolve().parent / "scan_calls.jsonl"


def gate_version(repo_root):
    return "ls@1"


def scan(component_id, repo_root):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"component_id": component_id, "repo_root": str(repo_root)}) + "\\n")
    return {
        "component_id": component_id,
        "gate_version": "ls@1",
        "evaluated": False,
        "reason": "no-reference-corpus",
        "similarity_score": None,
        "block_threshold": None,
        "blocked": False,
        "matches": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }
'''


SECRET_SRC = '''
import json
from pathlib import Path

_LOG = Path(__file__).resolve().parent / "scan_calls.jsonl"


def _record(kind, **kw):
    entry = {"kind": kind}
    entry.update({k: str(v) for k, v in kw.items()})
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\\n")


def _result(scope):
    return {
        "scope": scope,
        "gate_version": "ss@1",
        "flagged": False,
        "matches": [],
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def gate_version(repo_root):
    return "ss@1"


def scan(repo_root):
    _record("scan", repo_root=repo_root)
    return _result("full")


def scan_files(paths, repo_root=None):
    _record("scan_files", repo_root=repo_root)
    return _result("precommit")


def propose(repo_root):
    _record("propose", repo_root=repo_root)
    return {"allowlist": {"version": 1, "entries": []}, "ineligible": []}
'''


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

REQ_MD = """# R-FOO-001

**R-FOO-001** — `foo(x)` MUST return `2 * x`.
"""

AC_MD = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given x = 2
When foo(x) is called
Then it returns 4
```
"""

LIB_MD = """# Library

```
foo(x: int) -> int
```
"""

CONSTRAINTS_MD = """# Constraints

None.
"""


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_repo(repo_root: Path, assemble_raises: bool) -> dict:
    # Minimal spec corpus for comp-foo (harmless if unused).
    _write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    comp = repo_root / "specs" / "components" / "foo"
    _write(comp / "component.md", COMPONENT_MD)
    _write(comp / "requirements" / "R-FOO-001.md", REQ_MD)
    _write(comp / "acceptance" / "AC-FOO-001.md", AC_MD)
    _write(comp / "interface" / "library.md", LIB_MD)
    _write(comp / "constraints.md", CONSTRAINTS_MD)

    raise_line = 'raise ValueError("assemble-failed-sentinel")' if assemble_raises else "pass"
    assembler_src = ASSEMBLER_SRC.replace("RAISE_MARKER", raise_line)

    gen = repo_root / "gen"
    asm_dir = gen / "spec-bundle-assembler"
    _write(asm_dir / "spec_bundle_assembler.py", assembler_src)
    _write(repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py", COMPILER_SRC)
    _write(gen / "test-author" / "test_author.py", TEST_AUTHOR_SRC)
    _write(gen / "verifier-orchestrator" / "verifier_orchestrator.py", VERIFIER_SRC)
    lic_dir = gen / "license-scanner"
    _write(lic_dir / "license_scanner.py", LICENSE_SRC)
    sec_dir = gen / "secret-scanner"
    _write(sec_dir / "secret_scanner.py", SECRET_SRC)

    return {
        "assemble_log": asm_dir / "assemble_calls.jsonl",
        "license_scan_log": lic_dir / "scan_calls.jsonl",
        "secret_scan_log": sec_dir / "scan_calls.jsonl",
    }


def _read_log(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_current_provenance_key_reads_each_dependency_without_scanning(tmp_path):
    repo_root = tmp_path / "repo_ok"
    repo_root.mkdir()
    logs = _build_repo(repo_root, assemble_raises=False)

    key = provenance_checker.current_provenance_key("comp-foo", repo_root)

    assert field(key, "spec_bundle_hash") == "sha256:abc"

    calls = _read_log(logs["assemble_log"])
    assert calls, "faked assemble was never called"
    for call in calls:
        assert call["component_id"] == "comp-foo"
        assert call["mode"] == "cold"

    gate_versions = field(key, "gate_versions")
    assert dict(gate_versions) == {
        "compiler": "cc@1",
        "generated_test": "ta@1",
        "verifier": "vo@1",
        "license_scanner": "ls@1",
        "secret_scanner": "ss@1",
    }

    assert _read_log(logs["license_scan_log"]) == [], "license-scanner scan was called"
    assert _read_log(logs["secret_scan_log"]) == [], "secret-scanner scan was called"


def test_current_provenance_key_propagates_assemble_value_error(tmp_path):
    repo_root = tmp_path / "repo_raises"
    repo_root.mkdir()
    logs = _build_repo(repo_root, assemble_raises=True)

    with pytest.raises(ValueError, match="assemble-failed-sentinel"):
        provenance_checker.current_provenance_key("comp-foo", repo_root)

    assert _read_log(logs["assemble_log"]), "faked assemble was never called"
    assert _read_log(logs["license_scan_log"]) == []
    assert _read_log(logs["secret_scan_log"]) == []