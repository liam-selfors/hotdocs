# hotdocs-criterion: sha256:728be360cfa8f6262384febbdc5c4e5d04aab6767efac6fa35513d696baf1045
"""AC-IMPACT-006 (covers R-IMPACT-006).

Given an unchanged corpus and the same --changed argument,
when hotdocs impact runs twice in a row,
then both runs produce byte-identical BlastRadiusReport output.

Exercised through the documented library contract:
    compute_blast_radius(changed_ids: list[str], repo_root: Path) -> BlastRadiusReport
"""

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

import impact_analyzer


# ---------------------------------------------------------------------------
# Canonical serialization of a BlastRadiusReport (dict- or object-shaped).
# Kept as source text so the very same code runs in-process and in the
# subprocess runs below.
# ---------------------------------------------------------------------------

_SERIALIZER_SRC = r'''
import dataclasses as _dc
import enum as _enum
import json as _json
from pathlib import PurePath as _PurePath


def _to_plain(obj):
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, _enum.Enum):
        return _to_plain(obj.value)
    if isinstance(obj, _PurePath):
        return str(obj)
    if isinstance(obj, dict):
        return {str(k): _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        # A set has no inherent order; represent it canonically so only
        # genuine output differences are detected.
        return sorted((_to_plain(v) for v in obj), key=lambda x: _json.dumps(x, sort_keys=True))
    if _dc.is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _to_plain(getattr(obj, f.name)) for f in _dc.fields(obj)}
    if hasattr(obj, "__dict__"):
        return {k: _to_plain(v) for k, v in vars(obj).items() if not k.startswith("_")}
    return repr(obj)


def serialize_report(report):
    """Byte serialization preserving list order and key order."""
    return _json.dumps(_to_plain(report), ensure_ascii=False).encode("utf-8")
'''

_ns = {}
exec(_SERIALIZER_SRC, _ns)
serialize_report = _ns["serialize_report"]


def _field(value, name):
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _to_json_bytes(report):
    """If the report offers its own to_json(), capture that too."""
    if isinstance(report, dict):
        return None
    fn = getattr(report, "to_json", None)
    if not callable(fn):
        return None
    out = fn()
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    if isinstance(out, str):
        return out.encode("utf-8")
    return json.dumps(out, ensure_ascii=False).encode("utf-8")


# ---------------------------------------------------------------------------
# Synthetic, lint-clean corpus fixture
# ---------------------------------------------------------------------------

def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component(repo: Path, slug: str, depends_on=None, uses_var=None) -> None:
    upper = slug.upper()
    title = slug.capitalize()
    comp_dir = repo / "specs" / "components" / slug

    fm = [
        "---",
        f"id: comp-{slug}",
        f"title: {title}",
        "status: draft",
        "owners: [fixture-owner]",
        "sealed: true",
        f"source_path: legacy/{slug}",
    ]
    if depends_on:
        fm.append("depends_on: [" + ", ".join(depends_on) + "]")
    if uses_var:
        fm.append("uses_var: [" + ", ".join(uses_var) + "]")
    fm.append("---")

    body = textwrap.dedent(
        f"""
        # {title}

        ## Purpose

        {title} is a small fixture component used to exercise blast-radius
        computation. It matches existing behavior; do not regenerate.

        ## Scope

        - In scope: returning the fixture value.
        - Out of scope: everything else.

        ## Definitions

        None beyond the glossary.

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

        - Initial fixture version.
        """
    )
    _write(comp_dir / "component.md", "\n".join(fm) + "\n" + body)

    _write(
        comp_dir / "requirements" / f"R-{upper}-001.md",
        f"# R-{upper}-001\n\n"
        f"**R-{upper}-001** — The {slug} component MUST return the same "
        f"fixture value on every call.\n",
    )
    _write(
        comp_dir / "acceptance" / f"AC-{upper}-001.md",
        f"# AC-{upper}-001\n\n"
        f"Covers: R-{upper}-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        f"Given the {slug} component\n"
        "When its fixture value is requested twice\n"
        "Then both values are equal\n"
        "```\n",
    )
    _write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n"
        "```\n"
        f"{slug}_value() -> {title}Record\n"
        "```\n\n"
        f"Returns the fixture `{title}Record`.\n",
    )
    _write(
        comp_dir / "interface" / "data" / f"{title}Record.md",
        f"# `{title}Record`\n\n"
        "```json\n"
        '{ "value": 1 }\n'
        "```\n\n"
        "`value` is always the integer `1`.\n",
    )
    _write(
        comp_dir / "constraints.md",
        "# Constraints\n\n"
        f"- Latency: `{slug}_value()` MUST complete within 1 second, "
        "measured by timing a single call in a test.\n",
    )
    _write(repo / "legacy" / slug / f"{slug}.py", "VALUE = 1\n")


def _build_corpus(repo: Path) -> Path:
    repo.mkdir(parents=True, exist_ok=True)
    _write(
        repo / "specs" / "glossary.md",
        "# Glossary\n\n"
        "- **Fixture value** — the constant integer every fixture component returns.\n",
    )
    _write(
        repo / "specs" / "vars" / "VAR-FIXTURE-SETTING.md",
        "---\n"
        "id: VAR-FIXTURE-SETTING\n"
        "title: Fixture setting\n"
        "status: draft\n"
        "owners: [fixture-owner]\n"
        "---\n\n"
        "# VAR-FIXTURE-SETTING\n\n"
        "- name: VAR-FIXTURE-SETTING\n"
        "- required: optional\n"
        "- type: string\n"
        "- description: A non-secret setting read by fixture components.\n"
        "- sensitivity: non-secret\n"
        "- default: fixture\n",
    )
    # A diamond-plus-var shape so traversal order could plausibly matter.
    _component(repo, "alpha")
    _component(repo, "beta", depends_on=["comp-alpha"], uses_var=["VAR-FIXTURE-SETTING"])
    _component(repo, "gamma", depends_on=["comp-alpha"])
    _component(
        repo,
        "delta",
        depends_on=["comp-beta", "comp-gamma"],
        uses_var=["VAR-FIXTURE-SETTING"],
    )
    _component(repo, "epsilon", depends_on=["comp-delta"])
    return repo


# ---------------------------------------------------------------------------
# Lint precondition (spec-linter is loaded dynamically, never statically)
# ---------------------------------------------------------------------------

def _load_spec_linter():
    existing = sys.modules.get("spec_linter")
    if existing is not None and callable(getattr(existing, "lint", None)):
        return existing

    slug = "spec-linter"
    module_name = slug.replace("-", "_")
    start = Path(impact_analyzer.__file__).resolve()
    for parent in start.parents:
        flat = parent / "gen" / slug / f"{module_name}.py"
        pkg = parent / "gen" / slug / module_name / "__init__.py"
        if flat.is_file():
            spec = importlib.util.spec_from_file_location(module_name, flat)
        elif pkg.is_file():
            spec = importlib.util.spec_from_file_location(
                module_name, pkg, submodule_search_locations=[str(pkg.parent)]
            )
        else:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module  # register BEFORE exec_module
        spec.loader.exec_module(module)
        return module

    try:
        return importlib.import_module(module_name)
    except ImportError:
        return None


def _assert_lint_clean(repo_root: Path) -> None:
    spec_linter = _load_spec_linter()
    if spec_linter is not None and callable(getattr(spec_linter, "lint", None)):
        report = spec_linter.lint(None, repo_root)
        findings = _field(report, "findings") or []
        fails = [f for f in findings if _field(f, "severity") == "fail"]
        hard = _field(report, "hard_failures")
        if hard is None:
            summary = _field(report, "summary") or {}
            hard = _field(summary, "hard_failures")
        detail = [
            (_field(f, "rule_id"), _field(f, "file"), _field(f, "line"), _field(f, "message"))
            for f in fails
        ]
        assert not fails, f"fixture corpus is not lint-clean: {detail}"
        if hard is not None:
            assert hard == 0, f"fixture corpus reports {hard} hard failures: {detail}"


def _assert_answered(report, changed_ids):
    """The run answered the question (no precondition failure) and is non-trivial."""
    assert _field(report, "precondition_error") is None, (
        f"unexpected precondition_error: {_field(report, 'precondition_error')!r}"
    )
    impacted = _field(report, "impacted")
    assert impacted is not None, "report has no 'impacted' field"
    impacted = list(impacted)
    by_id = {_field(e, "component_id"): e for e in impacted}
    for cid in changed_ids:
        assert cid in by_id, f"{cid} missing from impacted: {list(by_id)}"
        assert _field(by_id[cid], "reason") == "direct"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "changed_ids",
    [
        ["comp-alpha"],
        ["comp-gamma", "comp-alpha"],
        ["comp-delta"],
    ],
)
def test_two_runs_in_a_row_are_byte_identical(tmp_path, changed_ids):
    repo_root = _build_corpus(tmp_path / "repo")
    _assert_lint_clean(repo_root)

    first = impact_analyzer.compute_blast_radius(list(changed_ids), repo_root)
    second = impact_analyzer.compute_blast_radius(list(changed_ids), repo_root)

    _assert_answered(first, changed_ids)
    _assert_answered(second, changed_ids)

    first_bytes = serialize_report(first)
    second_bytes = serialize_report(second)
    assert first_bytes == second_bytes, (
        f"runs differ:\n{first_bytes.decode()}\n!=\n{second_bytes.decode()}"
    )

    first_json = _to_json_bytes(first)
    second_json = _to_json_bytes(second)
    assert first_json == second_json

    # No dependence on wall-clock time: a later run (different second) is
    # still byte-identical.
    time.sleep(1.1)
    third = impact_analyzer.compute_blast_radius(list(changed_ids), repo_root)
    assert serialize_report(third) == first_bytes
    assert _to_json_bytes(third) == first_json


def test_runs_do_not_mutate_corpus(tmp_path):
    repo_root = _build_corpus(tmp_path / "repo")
    _assert_lint_clean(repo_root)

    def snapshot():
        return {
            str(p.relative_to(repo_root)): p.read_bytes()
            for p in sorted(repo_root.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts
        }

    before = snapshot()
    first = impact_analyzer.compute_blast_radius(["comp-alpha"], repo_root)
    middle = snapshot()
    second = impact_analyzer.compute_blast_radius(["comp-alpha"], repo_root)
    after = snapshot()

    assert before == middle == after, "compute_blast_radius changed the corpus it analyzed"
    assert serialize_report(first) == serialize_report(second)


_SUBPROCESS_SCRIPT = _SERIALIZER_SRC + r'''

import sys
from pathlib import Path
import impact_analyzer

_repo_root = Path(sys.argv[1])
_changed = _json.loads(sys.argv[2])
_report = impact_analyzer.compute_blast_radius(_changed, _repo_root)
sys.stdout.buffer.write(serialize_report(_report))
sys.stdout.flush()
'''


def _module_search_root() -> str:
    path = Path(impact_analyzer.__file__).resolve()
    if path.name == "__init__.py":
        return str(path.parent.parent)
    return str(path.parent)


def test_separate_process_runs_are_byte_identical(tmp_path):
    """Like two CLI invocations in a row: separate processes, different hash seeds."""
    repo_root = _build_corpus(tmp_path / "repo")
    _assert_lint_clean(repo_root)

    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    script = script_dir / "run_impact.py"
    script.write_text(_SUBPROCESS_SCRIPT, encoding="utf-8")

    search = [_module_search_root()] + [p for p in sys.path if isinstance(p, str) and p]
    changed = json.dumps(["comp-alpha", "comp-gamma"])

    outputs = []
    for seed in ("1", "4242"):
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(search)
        env["PYTHONHASHSEED"] = seed
        proc = subprocess.run(
            [sys.executable, str(script), str(repo_root), changed],
            cwd=str(tmp_path),
            env=env,
            capture_output=True,
            timeout=300,
        )
        assert proc.returncode == 0, (
            f"subprocess run failed (seed={seed}):\n{proc.stderr.decode(errors='replace')}"
        )
        outputs.append(proc.stdout)

    assert outputs[0], "subprocess produced no output"
    assert outputs[0] == outputs[1], (
        f"separate runs differ:\n{outputs[0].decode()}\n!=\n{outputs[1].decode()}"
    )

    in_process = impact_analyzer.compute_blast_radius(["comp-alpha", "comp-gamma"], repo_root)
    assert serialize_report(in_process) == outputs[0]