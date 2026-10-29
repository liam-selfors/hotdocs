"""AC-ASSEMBLE-007 — spec_bundle_hash is present and reproducible from the
bundle's own contents (covers R-ASSEMBLE-007)."""

import dataclasses
import hashlib
import importlib.util
import json
import re
import sys
import textwrap
from pathlib import Path

import pytest

import spec_bundle_assembler


COMPONENT_ID = "comp-hash-fixture"
COMPONENT_SLUG = "hash-fixture"


def _get(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


def _build_fixture(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        """
        ---
        id: glossary
        title: Glossary
        status: draft
        owners: [fixture-owner]
        ---

        # Glossary

        - **Widget** — a fixture-only term used by the hash fixture.
        """,
    )

    comp_dir = specs / "components" / COMPONENT_SLUG
    _write(
        comp_dir / "component.md",
        f"""
        ---
        id: {COMPONENT_ID}
        title: Hash Fixture
        status: draft
        owners: [fixture-owner]
        sealed: true
        source_path: legacy/hash_fixture.py
        depends_on: []
        ---

        # Hash Fixture

        ## Purpose

        A synthetic component used only to exercise spec bundle hashing.
        """,
    )
    _write(
        comp_dir / "requirements" / "R-HASHFIX-001.md",
        """
        # R-HASHFIX-001

        **R-HASHFIX-001** — The fixture MUST return a widget when asked.
        """,
    )
    _write(
        comp_dir / "acceptance" / "AC-HASHFIX-001.md",
        """
        # AC-HASHFIX-001

        Covers: R-HASHFIX-001
        Kind: generated-test

        ```gherkin
        Given a request for a widget
        When the fixture is asked
        Then it returns a widget
        ```
        """,
    )
    _write(
        comp_dir / "interface" / "library.md",
        """
        # Library

        ```
        get_widget() -> str
        ```
        """,
    )
    _write(
        comp_dir / "constraints.md",
        """
        # Constraints

        - No network access.
        """,
    )


def _load_lint():
    try:
        import spec_linter  # noqa: F401

        return spec_linter.lint
    except ImportError:
        pass
    # Fall back to the real repo's gen/spec-linter/, located relative to the
    # component under test's own module file (gen/<slug>/<module>.py).
    module_file = Path(spec_bundle_assembler.__file__).resolve()
    candidates = []
    for parent in module_file.parents:
        candidates.append(parent / "gen" / "spec-linter" / "spec_linter.py")
        candidates.append(
            parent / "gen" / "spec-linter" / "spec_linter" / "__init__.py"
        )
    for module_path in candidates:
        if module_path.is_file():
            spec = importlib.util.spec_from_file_location(
                "spec_linter", module_path
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules["spec_linter"] = module
            spec.loader.exec_module(module)
            return module.lint
    pytest.fail("could not locate spec_linter.lint to check the lint precondition")


_HARD_FAIL_VALUES = {"hard-fail", "hard_fail", "hardfail", "hard", "error", "fail"}


def _hard_fail_findings(report):
    if isinstance(report, (list, tuple)):
        findings = list(report)
    else:
        findings = _get(report, "findings", None)
        if findings is None:
            findings = _get(report, "hard_fails", None) or []
            return list(findings)
        findings = list(findings)
    hard = []
    for finding in findings:
        for key in ("severity", "level", "kind"):
            value = _get(finding, key, None)
            if value is None:
                continue
            value = getattr(value, "value", value)
            if str(value).lower() in _HARD_FAIL_VALUES:
                hard.append(finding)
                break
    return hard


def _bundle_to_dict(bundle):
    if isinstance(bundle, dict):
        return dict(bundle)
    if dataclasses.is_dataclass(bundle):
        return dataclasses.asdict(bundle)
    for method in ("to_dict", "model_dump", "dict", "_asdict"):
        fn = getattr(bundle, method, None)
        if callable(fn):
            try:
                result = fn()
            except TypeError:
                continue
            if isinstance(result, dict):
                return dict(result)
    return dict(vars(bundle))


def _jsonable(value):
    if isinstance(value, Path):
        return str(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _jsonable(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _strip_prefix(digest):
    digest = str(digest)
    return digest.split(":", 1)[1] if ":" in digest else digest


def _candidate_digests(bundle_dict):
    """Plausible canonical recomputations of the bundle's own content hash."""
    base = _jsonable(bundle_dict)
    payloads = []

    without_hash = {k: v for k, v in base.items() if k != "spec_bundle_hash"}
    payloads.append(without_hash)
    payloads.append({**without_hash, "spec_bundle_hash": None})
    payloads.append({**without_hash, "spec_bundle_hash": ""})
    without_hash_hint = {k: v for k, v in without_hash.items() if k != "hint_code"}
    payloads.append(without_hash_hint)

    digests = set()
    for payload in payloads:
        for dumps_kwargs in (
            {"sort_keys": True, "separators": (",", ":")},
            {"sort_keys": True, "separators": (",", ":"), "ensure_ascii": False},
            {"sort_keys": True},
            {"sort_keys": True, "ensure_ascii": False},
            {"sort_keys": True, "indent": 2},
            {"sort_keys": True, "indent": 2, "ensure_ascii": False},
        ):
            text = json.dumps(payload, **dumps_kwargs)
            digests.add(hashlib.sha256(text.encode("utf-8")).hexdigest())
    return digests


@pytest.fixture
def repo_root(tmp_path):
    _build_fixture(tmp_path)
    lint = _load_lint()
    report = lint(None, tmp_path)
    hard = _hard_fail_findings(report)
    assert hard == [], f"fixture corpus is not lint-clean: {hard!r}"
    return tmp_path


def test_spec_bundle_hash_present_and_reproducible(repo_root):
    bundle = spec_bundle_assembler.assemble(COMPONENT_ID, repo_root)

    assert _get(bundle, "component_id") == COMPONENT_ID

    spec_bundle_hash = _get(bundle, "spec_bundle_hash")
    assert spec_bundle_hash, "spec_bundle_hash must be present and non-empty"
    assert isinstance(spec_bundle_hash, str)
    assert re.fullmatch(r"(sha256:)?[0-9a-f]{64}", spec_bundle_hash), (
        f"spec_bundle_hash is not a sha256 content hash: {spec_bundle_hash!r}"
    )

    bundle_dict = _bundle_to_dict(bundle)
    recomputed = _candidate_digests(bundle_dict)
    assert _strip_prefix(spec_bundle_hash) in recomputed, (
        "recomputing spec_bundle_hash from the bundle's own contents did not "
        f"reproduce {spec_bundle_hash!r}"
    )


def test_spec_bundle_hash_stable_across_reassembly(repo_root):
    first = spec_bundle_assembler.assemble(COMPONENT_ID, repo_root)
    second = spec_bundle_assembler.assemble(COMPONENT_ID, repo_root)

    first_hash = _get(first, "spec_bundle_hash")
    second_hash = _get(second, "spec_bundle_hash")
    assert first_hash
    assert first_hash == second_hash


def test_spec_bundle_hash_tracks_bundle_contents(repo_root):
    before = spec_bundle_assembler.assemble(COMPONENT_ID, repo_root)
    before_hash = _get(before, "spec_bundle_hash")

    constraints = (
        repo_root / "specs" / "components" / COMPONENT_SLUG / "constraints.md"
    )
    constraints.write_text(
        constraints.read_text(encoding="utf-8") + "- No disk writes.\n",
        encoding="utf-8",
    )

    after = spec_bundle_assembler.assemble(COMPONENT_ID, repo_root)
    after_hash = _get(after, "spec_bundle_hash")

    assert after_hash
    assert after_hash != before_hash
    assert _strip_prefix(after_hash) in _candidate_digests(_bundle_to_dict(after))