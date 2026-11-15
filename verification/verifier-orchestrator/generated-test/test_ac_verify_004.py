"""AC-VERIFY-004 (Covers: R-VERIFY-004).

Given a component whose gen/<component>/ public interface does not match
its interface/ contract, when verify runs, then interface_drift is true and
the overall verdict is fail.
"""

import verifier_orchestrator

from pathlib import Path

import pytest


SLUG = "widget"
COMPONENT_ID = "comp-widget"
MODULE_NAME = "widget"
CRITERION_ID = "AC-WIDGET-001"
CACHED_TEST_NAME = "test_ac_widget_001.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FAKE_ASSEMBLER = (
    "import hashlib\n"
    "from dataclasses import dataclass, field\n"
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def _read(p):\n"
    "    p = Path(p)\n"
    "    return p.read_text(encoding='utf-8') if p.is_file() else ''\n"
    "\n"
    "\n"
    "def _slug(component_id):\n"
    "    return component_id[len('comp-'):] if component_id.startswith('comp-') else component_id\n"
    "\n"
    "\n"
    "def _join(texts):\n"
    "    return '\\n\\n'.join(t.strip() for t in texts if t and t.strip())\n"
    "\n"
    "\n"
    "def _interface_text(base):\n"
    "    texts = []\n"
    "    idir = base / 'interface'\n"
    "    if idir.is_dir():\n"
    "        for p in sorted(idir.rglob('*.md')):\n"
    "            texts.append(_read(p))\n"
    "    return _join(texts)\n"
    "\n"
    "\n"
    "class _Mapping:\n"
    "    def __getitem__(self, key):\n"
    "        try:\n"
    "            return getattr(self, key)\n"
    "        except AttributeError:\n"
    "            raise KeyError(key)\n"
    "\n"
    "    def get(self, key, default=None):\n"
    "        return getattr(self, key, default)\n"
    "\n"
    "    def keys(self):\n"
    "        return list(self.__dataclass_fields__.keys())\n"
    "\n"
    "    def __contains__(self, key):\n"
    "        return key in self.__dataclass_fields__\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class SpecBundle(_Mapping):\n"
    "    component_id: str\n"
    "    spec_bundle_hash: str\n"
    "    spec: str\n"
    "    interface: str\n"
    "    constraints: str\n"
    "    dependency_interfaces: dict = field(default_factory=dict)\n"
    "    dependency_context: dict = field(default_factory=dict)\n"
    "    dependency_usage: dict = field(default_factory=dict)\n"
    "    vars: dict = field(default_factory=dict)\n"
    "    glossary: str = ''\n"
    "    hint_code: object = None\n"
    "\n"
    "\n"
    "@dataclass\n"
    "class CriterionBundle(_Mapping):\n"
    "    component_id: str\n"
    "    criterion_id: str\n"
    "    covers: str\n"
    "    criterion_text: str\n"
    "    requirement_text: str\n"
    "    interface: str\n"
    "    glossary: str\n"
    "    dependency_interfaces: dict = field(default_factory=dict)\n"
    "\n"
    "\n"
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    repo_root = Path(repo_root)\n"
    "    base = repo_root / 'specs' / 'components' / _slug(component_id)\n"
    "    reqs = [_read(p) for p in sorted((base / 'requirements').glob('*.md'))]\n"
    "    spec = _join([_read(base / 'component.md')] + reqs)\n"
    "    interface = _interface_text(base)\n"
    "    constraints = _join([_read(base / 'constraints.md')])\n"
    "    glossary = _join([_read(repo_root / 'specs' / 'glossary.md')])\n"
    "    digest = hashlib.sha256((spec + interface + constraints + glossary).encode('utf-8')).hexdigest()\n"
    "    hint = None\n"
    "    if mode == 'hint':\n"
    "        hint = {}\n"
    "        gdir = repo_root / 'gen' / _slug(component_id)\n"
    "        if gdir.is_dir():\n"
    "            for p in sorted(gdir.rglob('*')):\n"
    "                if p.is_file():\n"
    "                    hint[str(p.relative_to(gdir))] = _read(p)\n"
    "    return SpecBundle(\n"
    "        component_id=component_id,\n"
    "        spec_bundle_hash='sha256:' + digest,\n"
    "        spec=spec,\n"
    "        interface=interface,\n"
    "        constraints=constraints,\n"
    "        glossary=glossary,\n"
    "        hint_code=hint,\n"
    "    )\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    repo_root = Path(repo_root)\n"
    "    base = repo_root / 'specs' / 'components' / _slug(component_id)\n"
    "    ac_text = _read(base / 'acceptance' / (criterion_id + '.md'))\n"
    "    covers = ''\n"
    "    for line in ac_text.splitlines():\n"
    "        if line.startswith('Covers:'):\n"
    "            covers = line.split(':', 1)[1].strip()\n"
    "            break\n"
    "    req_text = _read(base / 'requirements' / (covers + '.md')) if covers else ''\n"
    "    return CriterionBundle(\n"
    "        component_id=component_id,\n"
    "        criterion_id=criterion_id,\n"
    "        covers=covers,\n"
    "        criterion_text=ac_text.strip(),\n"
    "        requirement_text=req_text.strip(),\n"
    "        interface=_interface_text(base),\n"
    "        glossary=_join([_read(repo_root / 'specs' / 'glossary.md')]),\n"
    "        dependency_interfaces={},\n"
    "    )\n"
)


PASSING_CACHED_TEST = (
    "def test_placeholder_passes():\n"
    "    assert True\n"
)


def _build_fixture(repo_root: Path, gen_source: str) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )

    _write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Widget capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets can be widened.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widening widgets.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "\n"
        "```gherkin\n"
        "Given a widget of width 2\n"
        "When it is widened by 3\n"
        "Then its width is 5\n"
        "```\n",
    )

    base = repo_root / "specs" / "components" / SLUG
    _write(
        base / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget adds two widths.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widening.\n"
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
        base / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — `widen(x, y)` MUST return `x + y`.\n",
    )
    _write(
        base / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2 and y = 3\n"
        "When widen(x, y) is called\n"
        "Then it returns 5\n"
        "```\n",
    )
    _write(
        base / "interface" / "library.md",
        "# Library\n\n```\nwiden(x: int, y: int) -> int\n```\n",
    )
    _write(base / "constraints.md", "# Constraints\n\nNone.\n")

    # The generated code under test.
    _write(repo_root / "gen" / SLUG / f"{MODULE_NAME}.py", gen_source)

    # A cached, trivially-passing generated test so the criterion itself
    # is not the reason for any failure.
    _write(
        repo_root / "verification" / SLUG / "generated-test" / CACHED_TEST_NAME,
        PASSING_CACHED_TEST,
    )

    # Planted fake spec-bundle-assembler (flat-module shape).
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        FAKE_ASSEMBLER,
    )


def _fake_test_author(bundle):
    # Fallback only: should a cached test not be honoured, supply the same
    # trivially-passing test in test-author's TestAuthoringResult shape.
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "model": "fake-model",
        "seed": 0,
        "prompt_version": "v1",
        "cache_hit": False,
        "file": {
            "path": f"verification/{SLUG}/generated-test/{CACHED_TEST_NAME}",
            "content": PASSING_CACHED_TEST,
        },
        "model_call_error": None,
    }


DRIFTED_SOURCES = {
    # A documented parameter is missing from the generated callable.
    "parameter-mismatch": (
        "def widen(x):\n"
        "    return x\n"
    ),
    # The documented callable does not exist at all.
    "missing-callable": (
        "def broaden(x, y):\n"
        "    return x + y\n"
    ),
}


@pytest.mark.parametrize("case", sorted(DRIFTED_SOURCES))
def test_interface_drift_is_true_and_overall_fails(tmp_path, case):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root, DRIFTED_SOURCES[case])

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=_fake_test_author
    )

    assert field(report, "interface_drift") is True
    assert field(report, "overall") == "fail"


def test_matching_interface_reports_no_drift(tmp_path):
    # Control: the same fixture with a gen/ module that matches its
    # interface/ contract (plus an undocumented extra public helper, which
    # is not drift) must not report interface drift.
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(
        repo_root,
        "def widen(x, y):\n"
        "    return x + y\n"
        "\n"
        "\n"
        "def undocumented_helper(z):\n"
        "    return z\n",
    )

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=_fake_test_author
    )

    assert field(report, "interface_drift") is False