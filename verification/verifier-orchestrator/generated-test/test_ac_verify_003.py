import json
import os
import socket
from pathlib import Path

import pytest

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


GLOSSARY = """# Glossary

- **Widget** — a test term.
"""

PRODUCT = """---
id: P-WIDGETS
title: Widgets
status: draft
owners: [team-a]
---

# Widgets

## Purpose

Widgets double numbers.

## Scope

- In scope: doubling.

### CS-WIDGETS-001

Covers: P-WIDGETS
Kind: llm-judge

```gherkin
Given a widget system
When a number is doubled
Then the result is twice the input
```
"""

COMPONENT = """---
id: comp-widget
title: Widget
status: draft
owners: [team-a]
realizes: [P-WIDGETS]
depends_on: []
---

# Widget

## Purpose

Widget doubles a number.

## Scope

- In scope: doubling a number.

## Definitions

None.

## Behavior

See `requirements/`.

## Interfaces

See `interface/`.

## Data

See `interface/data/`.

## Acceptance criteria

See `acceptance/`.

## Non-functional constraints

See `constraints.md`.

## Open questions

## Change log

- Initial draft.
"""

REQUIREMENT = """# R-WIDGET-001

**R-WIDGET-001** — The specification of `double_it(x)` MUST be clear and unambiguous.
"""

ACCEPTANCE = """# AC-WIDGET-001

Covers: R-WIDGET-001
Kind: llm-judge

```gherkin
Given the widget component's specification
When a reviewer reads the description of double_it
Then the description is clear and unambiguous
```
"""

LIBRARY = """# Library

```
double_it(x: int) -> int
```
"""

CONSTRAINTS = """# Constraints

None.
"""

GEN_CODE = """def double_it(x):
    return 2 * x
"""


FAKE_ASSEMBLER = '''
import json
from pathlib import Path

_LOG = {log!r}


def _log(record):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


class _MappingMixin:
    _FIELDS = ()

    def __getitem__(self, key):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self._FIELDS:
            return getattr(self, key)
        return default

    def keys(self):
        return list(self._FIELDS)

    def __iter__(self):
        return iter(self._FIELDS)

    def __len__(self):
        return len(self._FIELDS)

    def __contains__(self, key):
        return key in self._FIELDS


class SpecBundle(_MappingMixin):
    _FIELDS = (
        "component_id", "spec_bundle_hash", "spec", "interface", "constraints",
        "dependency_interfaces", "dependency_context", "dependency_usage",
        "vars", "glossary", "hint_code",
    )

    def __init__(self, component_id, spec_bundle_hash, spec, interface, constraints,
                 dependency_interfaces=None, dependency_context=None,
                 dependency_usage=None, vars=None, glossary="", hint_code=None):
        self.component_id = component_id
        self.spec_bundle_hash = spec_bundle_hash
        self.spec = spec
        self.interface = interface
        self.constraints = constraints
        self.dependency_interfaces = dependency_interfaces or {{}}
        self.dependency_context = dependency_context or {{}}
        self.dependency_usage = dependency_usage or {{}}
        self.vars = vars or {{}}
        self.glossary = glossary
        self.hint_code = hint_code


class CriterionBundle(_MappingMixin):
    _FIELDS = (
        "component_id", "criterion_id", "covers", "criterion_text",
        "requirement_text", "interface", "glossary", "dependency_interfaces",
    )

    def __init__(self, component_id, criterion_id, covers, criterion_text,
                 requirement_text, interface, glossary, dependency_interfaces=None):
        self.component_id = component_id
        self.criterion_id = criterion_id
        self.covers = covers
        self.criterion_text = criterion_text
        self.requirement_text = requirement_text
        self.interface = interface
        self.glossary = glossary
        self.dependency_interfaces = dependency_interfaces or {{}}


def _comp_dir(component_id, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    return Path(repo_root) / "specs" / "components" / slug


def _read(p):
    p = Path(p)
    return p.read_text(encoding="utf-8").strip() if p.is_file() else ""


def assemble(component_id, repo_root, mode="cold"):
    _log({{"fn": "assemble", "component_id": component_id}})
    d = _comp_dir(component_id, repo_root)
    reqs = "\\n\\n".join(_read(p) for p in sorted((d / "requirements").glob("*.md")))
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "0" * 64,
        spec=_read(d / "component.md") + "\\n\\n" + reqs,
        interface=_read(d / "interface" / "library.md"),
        constraints=_read(d / "constraints.md"),
        glossary=_read(Path(repo_root) / "specs" / "glossary.md"),
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log({{"fn": "assemble_criterion", "component_id": component_id,
           "criterion_id": criterion_id}})
    d = _comp_dir(component_id, repo_root)
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-WIDGET-001",
        criterion_text=_read(d / "acceptance" / (criterion_id + ".md")),
        requirement_text=_read(d / "requirements" / "R-WIDGET-001.md"),
        interface=_read(d / "interface" / "library.md"),
        glossary=_read(Path(repo_root) / "specs" / "glossary.md"),
        dependency_interfaces={{}},
    )
'''

FAKE_LLM_ENDPOINT = '''
import json

_LOG = {log!r}


def complete(*args, **kwargs):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"fn": "complete", "args": [repr(a) for a in args],
                             "kwargs": sorted(kwargs)}}) + "\\n")
    return "{{\\"result\\": \\"pass\\", \\"rationale\\": \\"fake model output\\"}}"
'''

FAKE_TEST_AUTHOR = '''
import json

_LOG = {log!r}


def author_test(bundle, model, seed=0, *, repo_root=None, llm_backend=None):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({{"fn": "author_test", "model": repr(model)}}) + "\\n")
    return {{
        "component_id": "comp-widget",
        "criterion_id": "AC-WIDGET-001",
        "model": model,
        "seed": seed,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": None,
        "model_call_error": "fake test-author must not be called",
    }}
'''


def _build_fixture(repo_root: Path, log_dir: Path) -> dict:
    _write(repo_root / "specs" / "glossary.md", GLOSSARY)
    _write(repo_root / "specs" / "product" / "widgets.md", PRODUCT)
    comp = repo_root / "specs" / "components" / "widget"
    _write(comp / "component.md", COMPONENT)
    _write(comp / "requirements" / "R-WIDGET-001.md", REQUIREMENT)
    _write(comp / "acceptance" / "AC-WIDGET-001.md", ACCEPTANCE)
    _write(comp / "interface" / "library.md", LIBRARY)
    _write(comp / "constraints.md", CONSTRAINTS)
    _write(repo_root / "gen" / "widget" / "widget.py", GEN_CODE)

    logs = {
        "assembler": log_dir / "assembler.log",
        "llm": log_dir / "llm_endpoint.log",
        "test_author": log_dir / "test_author.log",
    }
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        FAKE_ASSEMBLER.format(log=str(logs["assembler"])),
    )
    _write(
        repo_root / "gen" / "llm-endpoint" / "llm_endpoint.py",
        FAKE_LLM_ENDPOINT.format(log=str(logs["llm"])),
    )
    _write(
        repo_root / "gen" / "test-author" / "test_author.py",
        FAKE_TEST_AUTHOR.format(log=str(logs["test_author"])),
    )
    return logs


def _read_log(path: Path) -> list:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_llm_judge_criterion_skipped_with_null_rationale_when_no_judge(tmp_path, monkeypatch):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    logs = _build_fixture(repo_root, log_dir)

    # Remove any credentials a model provider could use.
    for var in (
        "ANTHROPIC_API_KEY",
        "VAR_ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)

    # Record (and block) any outbound network connection attempt made in-process.
    network_attempts = []
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def _is_inet(sock):
        return sock.family in (socket.AF_INET, getattr(socket, "AF_INET6", socket.AF_INET))

    def guarded_connect(self, address):
        if _is_inet(self):
            network_attempts.append(repr(address))
            raise OSError("network access blocked by test")
        return real_connect(self, address)

    def guarded_connect_ex(self, address):
        if _is_inet(self):
            network_attempts.append(repr(address))
            raise OSError("network access blocked by test")
        return real_connect_ex(self, address)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)

    monkeypatch.chdir(repo_root)

    # No judge configured: judge omitted entirely.
    report = verifier_orchestrator.verify("comp-widget", repo_root)

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == "AC-WIDGET-001"]
    assert len(matching) == 1, f"expected exactly one AC-WIDGET-001 entry, got {criteria!r}"
    entry = matching[0]

    assert field(entry, "kind") == "llm-judge"
    assert field(entry, "result") == "skipped", f"expected skipped, got {entry!r}"
    if isinstance(entry, dict):
        assert "rationale" in entry, f"skipped llm-judge entry must carry a null rationale: {entry!r}"
        assert entry["rationale"] is None
    else:
        assert getattr(entry, "rationale") is None

    # The JSON form agrees.
    if hasattr(report, "to_dict"):
        as_dict = report.to_dict()
        json_entries = [c for c in as_dict["criteria"] if c["id"] == "AC-WIDGET-001"]
        assert len(json_entries) == 1
        assert json_entries[0]["result"] == "skipped"
        assert "rationale" in json_entries[0]
        assert json_entries[0]["rationale"] is None

    # verify did not call a model itself to produce that result.
    assert _read_log(logs["llm"]) == [], "verify invoked a model via llm-endpoint"
    assert _read_log(logs["test_author"]) == [], "verify invoked test-author for an llm-judge criterion"
    assert network_attempts == [], f"verify attempted network access: {network_attempts!r}"
    calls_dir = repo_root / ".hotdocs" / "calls"
    if calls_dir.exists():
        recorded = [p for p in calls_dir.rglob("*") if p.is_file()]
        assert recorded == [], f"model call records were written: {recorded!r}"