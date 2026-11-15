import json
import re
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FAKE_ASSEMBLER = '''\
from pathlib import Path


class _Bundle:
    _FIELDS = ()

    def __init__(self, **kwargs):
        for name in self._FIELDS:
            setattr(self, name, kwargs.get(name))

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


class SpecBundle(_Bundle):
    _FIELDS = (
        "component_id", "spec_bundle_hash", "spec", "interface", "constraints",
        "dependency_interfaces", "dependency_context", "dependency_usage",
        "vars", "glossary", "hint_code",
    )


class CriterionBundle(_Bundle):
    _FIELDS = (
        "component_id", "criterion_id", "covers", "criterion_text",
        "requirement_text", "interface", "glossary", "dependency_interfaces",
    )


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def _read(path):
    p = Path(path)
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def _interface(comp_dir):
    parts = []
    idir = comp_dir / "interface"
    if idir.is_dir():
        for p in sorted(idir.rglob("*.md")):
            parts.append(p.read_text(encoding="utf-8").strip())
    return "\\n\\n".join(x for x in parts if x)


def assemble(component_id, repo_root, mode="cold"):
    repo_root = Path(repo_root)
    comp_dir = repo_root / "specs" / "components" / _slug(component_id)
    spec_parts = [_read(comp_dir / "component.md").strip()]
    rdir = comp_dir / "requirements"
    if rdir.is_dir():
        for p in sorted(rdir.glob("R-*.md")):
            spec_parts.append(p.read_text(encoding="utf-8").strip())
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "0" * 64,
        spec="\\n\\n".join(x for x in spec_parts if x),
        interface=_interface(comp_dir),
        constraints=_read(comp_dir / "constraints.md").strip(),
        dependency_interfaces={},
        dependency_context={},
        dependency_usage={},
        vars={},
        glossary=_read(repo_root / "specs" / "glossary.md").strip(),
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    repo_root = Path(repo_root)
    comp_dir = repo_root / "specs" / "components" / _slug(component_id)
    text = _read(comp_dir / "acceptance" / (criterion_id + ".md"))
    covers = ""
    for line in text.splitlines():
        if line.startswith("Covers:"):
            covers = line.split(":", 1)[1].strip()
            break
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers=covers,
        criterion_text=text,
        requirement_text=_read(comp_dir / "requirements" / (covers + ".md")),
        interface=_interface(comp_dir),
        glossary=_read(repo_root / "specs" / "glossary.md").strip(),
        dependency_interfaces={},
    )
'''


GHERKIN = {
    "AC-FOO-001": (
        "Given the number two is supplied to the doubling routine\n"
        "When double is called with that number\n"
        "Then the doubling routine answers four"
    ),
    "AC-FOO-002": (
        "Given the number five is supplied to the doubling routine\n"
        "When double is called with that number\n"
        "Then the doubling routine answers ten"
    ),
    "AC-FOO-003": (
        "Given a negative operand minus three is supplied\n"
        "When double is called with the negative operand\n"
        "Then the doubling routine answers minus six"
    ),
    "AC-FOO-004": (
        "Given the Foo specification text is reviewed\n"
        "When a reviewer reads its requirements\n"
        "Then the wording about doubling is unambiguous and clear"
    ),
}


def _acceptance(ac_id: str, covers: str, kind: str) -> str:
    return (
        f"# {ac_id}\n"
        "\n"
        f"Covers: {covers}\n"
        f"Kind: {kind}\n"
        "\n"
        "```gherkin\n"
        f"{GHERKIN[ac_id]}\n"
        "```\n"
    )


def _build_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    _write(
        repo_root / "specs" / "product" / "foo-capability.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo Capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Foo Capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubling numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-FOO-001\n"
        "Covers: P-FOO\n"
        "Kind: llm-judge\n"
        "\n"
        "```gherkin\n"
        "Given the assembled system is available\n"
        "When a user asks it to double a number\n"
        "Then the system answers with twice that number\n"
        "```\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-FOO]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling integers.\n"
        "\n"
        "## Definitions\n"
        "\n"
        "None.\n"
        "\n"
        "## Behavior\n"
        "\n"
        "See `requirements/`.\n"
        "\n"
        "## Interfaces\n"
        "\n"
        "See `interface/`.\n"
        "\n"
        "## Data\n"
        "\n"
        "See `interface/data/`.\n"
        "\n"
        "## Acceptance criteria\n"
        "\n"
        "See `acceptance/`.\n"
        "\n"
        "## Non-functional constraints\n"
        "\n"
        "See `constraints.md`.\n"
        "\n"
        "## Open questions\n"
        "\n"
        "## Change log\n"
        "\n"
        "- Initial draft.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n\n**R-FOO-001** — `double(x)` MUST return `2 * x` for positive `x`.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n\n**R-FOO-002** — `double(x)` MUST return `2 * x` for negative `x`.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-003.md",
        "# R-FOO-003\n\n**R-FOO-003** — The specification of `double` MUST be unambiguous.\n",
    )
    _write(comp / "acceptance" / "AC-FOO-001.md", _acceptance("AC-FOO-001", "R-FOO-001", "generated-test"))
    _write(comp / "acceptance" / "AC-FOO-002.md", _acceptance("AC-FOO-002", "R-FOO-001", "generated-test"))
    _write(comp / "acceptance" / "AC-FOO-003.md", _acceptance("AC-FOO-003", "R-FOO-002", "generated-test"))
    _write(comp / "acceptance" / "AC-FOO-004.md", _acceptance("AC-FOO-004", "R-FOO-003", "llm-judge"))
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble(x: int) -> int\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # The component's real code.
    _write(repo_root / "gen" / "foo" / "foo.py", "def double(x):\n    return 2 * x\n")

    # Cached generated tests (Criterion test filename convention).
    gt = repo_root / "verification" / "foo" / "generated-test"
    _write(
        gt / "test_ac_foo_001.py",
        "def test_ac_foo_001():\n    assert 2 * 2 == 4\n",
    )
    _write(
        gt / "test_ac_foo_002.py",
        "def test_ac_foo_002():\n    assert 5 * 2 == 10\n",
    )
    _write(
        gt / "test_ac_foo_003.py",
        "def test_ac_foo_003():\n"
        "    expected_marker_value = 'EXPECTED-SENTINEL-VALUE'\n"
        "    actual_marker_value = 'ACTUAL-SENTINEL-VALUE'\n"
        "    assert actual_marker_value == expected_marker_value\n",
    )

    # Fake spec-bundle-assembler dependency, planted at the repo-root path.
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        FAKE_ASSEMBLER,
    )


def _strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for k, v in value.items():
            yield from _strings_in(k)
            yield from _strings_in(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _strings_in(v)
    elif value is not None and not isinstance(value, bool):
        yield str(value)


def test_requirement_results_projection_is_boolean_only(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    report = verifier_orchestrator.verify("comp-foo", repo_root)

    requirement_results = field(report, "requirement_results")
    assert isinstance(requirement_results, dict)

    expected = {"R-FOO-001": "pass", "R-FOO-002": "fail", "R-FOO-003": "fail"}
    assert dict(requirement_results) == expected

    # The JSON form carries the same projection.
    as_dict = report.to_dict()
    assert as_dict["requirement_results"] == expected

    # Only R-id keys and pass/fail values, nothing nested.
    for key, value in requirement_results.items():
        assert isinstance(key, str) and re.fullmatch(r"R-[A-Z0-9]+-\d{3}", key), key
        assert value in ("pass", "fail"), value

    serialized = json.dumps(requirement_results, sort_keys=True)

    # No Gherkin text anywhere in it.
    for keyword in ("Given", "When", "Then", "gherkin"):
        assert keyword not in serialized
    for text in GHERKIN.values():
        for line in text.splitlines():
            assert line not in serialized
            step_body = line.split(" ", 1)[1]
            assert step_body not in serialized

    # No rationale, failure detail, or expected/actual values anywhere in it.
    for forbidden_key in ("rationale", "failure_detail", "expected", "actual", "message"):
        assert forbidden_key not in serialized
    assert "EXPECTED-SENTINEL-VALUE" not in serialized
    assert "ACTUAL-SENTINEL-VALUE" not in serialized

    criteria = field(report, "criteria")
    allowed = set(expected) | {"pass", "fail"}
    for c in criteria:
        for extra_key in ("rationale", "failure_detail"):
            extra = c.get(extra_key) if isinstance(c, dict) else getattr(c, extra_key, None)
            if extra is None:
                continue
            for s in _strings_in(extra):
                if s in allowed or len(s) < 5:
                    continue
                assert s not in serialized, (extra_key, s)