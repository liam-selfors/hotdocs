import json
import uuid
from pathlib import Path

import pytest

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _expected_bundle_fields(nonce: str) -> dict:
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQUIREMENT_ID,
        "criterion_text": "criterion-text-" + nonce,
        "requirement_text": "requirement-text-" + nonce,
        "interface": "interface-text-" + nonce,
        "glossary": "glossary-text-" + nonce,
        "dependency_interfaces": {"comp-sentinel-dep": "sentinel-interface-" + nonce},
    }


def _fake_assembler_source(nonce: str, log_path: Path) -> str:
    return (
        "import json\n"
        "from dataclasses import dataclass, field, fields\n"
        "\n"
        "NONCE = " + repr(nonce) + "\n"
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "\n"
        "\n"
        "def _log(record):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(json.dumps(record) + '\\n')\n"
        "\n"
        "\n"
        "class _MappingMixin:\n"
        "    def __getitem__(self, key):\n"
        "        if key not in self.keys():\n"
        "            raise KeyError(key)\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def get(self, key, default=None):\n"
        "        if key not in self.keys():\n"
        "            return default\n"
        "        return getattr(self, key)\n"
        "\n"
        "    def keys(self):\n"
        "        return [f.name for f in fields(self)]\n"
        "\n"
        "    def items(self):\n"
        "        return [(k, getattr(self, k)) for k in self.keys()]\n"
        "\n"
        "    def values(self):\n"
        "        return [getattr(self, k) for k in self.keys()]\n"
        "\n"
        "    def __iter__(self):\n"
        "        return iter(self.keys())\n"
        "\n"
        "    def __len__(self):\n"
        "        return len(self.keys())\n"
        "\n"
        "    def __contains__(self, key):\n"
        "        return key in self.keys()\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class CriterionBundle(_MappingMixin):\n"
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
        "CriterionBundle.FAKE_MARKER = 'fake-assembler-' + NONCE\n"
        "\n"
        "\n"
        "@dataclass\n"
        "class SpecBundle(_MappingMixin):\n"
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
        "def assemble(component_id, repo_root, mode='cold'):\n"
        "    _log({'fn': 'assemble', 'args': [component_id, str(repo_root), mode]})\n"
        "    return SpecBundle(\n"
        "        component_id=component_id,\n"
        "        spec_bundle_hash='sha256:' + '0' * 64,\n"
        "        spec='spec-text-' + NONCE,\n"
        "        interface='interface-text-' + NONCE,\n"
        "        constraints='None.',\n"
        "        dependency_interfaces={},\n"
        "        dependency_context={},\n"
        "        dependency_usage={},\n"
        "        vars={},\n"
        "        glossary='glossary-text-' + NONCE,\n"
        "        hint_code=None,\n"
        "    )\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    _log({'fn': 'assemble_criterion', 'args': [component_id, criterion_id, str(repo_root)]})\n"
        "    return CriterionBundle(\n"
        "        component_id=component_id,\n"
        "        criterion_id=criterion_id,\n"
        "        covers=" + repr(REQUIREMENT_ID) + ",\n"
        "        criterion_text='criterion-text-' + NONCE,\n"
        "        requirement_text='requirement-text-' + NONCE,\n"
        "        interface='interface-text-' + NONCE,\n"
        "        glossary='glossary-text-' + NONCE,\n"
        "        dependency_interfaces={'comp-sentinel-dep': 'sentinel-interface-' + NONCE},\n"
        "    )\n"
    )


def _build_fixture(repo_root: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Widget term** — a test term.\n",
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
        "Numbers can be doubled.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
        "\n"
        "### CS-WIDGET-001\n"
        "\n"
        "Covers: P-WIDGET\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a number two\n"
        "When it is doubled\n"
        "Then the outcome is four\n"
        "```\n",
    )
    comp = repo_root / "specs" / "components" / SLUG
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "realizes: [P-WIDGET]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widget doubles a number.\n"
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
        comp / "requirements" / "R-WIDGET-001.md",
        "# R-WIDGET-001\n\n**R-WIDGET-001** — `double_it(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp / "acceptance" / "AC-WIDGET-001.md",
        "# AC-WIDGET-001\n"
        "\n"
        "Covers: R-WIDGET-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given an integer two\n"
        "When double_it is called on it\n"
        "Then it returns four\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble_it(x: int) -> int\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    _write(
        repo_root / "gen" / SLUG / "widget.py",
        "def double_it(x):\n    return 2 * x\n",
    )


def _generated_test_code(gen_dir: Path, marker: Path, assertion: str) -> str:
    return (
        "import sys\n"
        "from pathlib import Path\n"
        "\n"
        "try:\n"
        "    import widget\n"
        "except ImportError:\n"
        "    sys.path.append(" + repr(str(gen_dir)) + ")\n"
        "    import widget\n"
        "\n"
        "\n"
        "def test_ac_widget_001():\n"
        "    with open(" + repr(str(marker)) + ", 'a', encoding='utf-8') as fh:\n"
        "        fh.write('ran\\n')\n"
        "    " + assertion + "\n"
    )


@pytest.mark.parametrize(
    "assertion, expected_result",
    [
        ("assert widget.double_it(2) == 4", "pass"),
        ("assert widget.double_it(2) == 5", "fail"),
    ],
)
def test_generated_test_dispatches_assembler_bundle_and_executes_returned_code(
    tmp_path, assertion, expected_result
):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_fixture(repo_root)

    nonce = uuid.uuid4().hex
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    assembler_log = log_dir / "assembler.jsonl"
    marker = log_dir / "generated_test_ran.txt"

    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        _fake_assembler_source(nonce, assembler_log),
    )

    cached = (
        repo_root / "verification" / SLUG / "generated-test" / "test_ac_widget_001.py"
    )
    assert not cached.exists()

    test_code = _generated_test_code(repo_root / "gen" / SLUG, marker, assertion)
    rel_path = "verification/" + SLUG + "/generated-test/test_ac_widget_001.py"

    received = []

    def mock_test_author(*args, **kwargs):
        received.append((args, kwargs))
        out = repo_root / rel_path
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(test_code, encoding="utf-8")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "mock-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {"path": rel_path, "content": test_code},
            "model_call_error": None,
        }

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=mock_test_author
    )

    # test_author invoked exactly once, with exactly one bundle argument.
    assert len(received) == 1
    args, kwargs = received[0]
    assert len(args) + len(kwargs) == 1
    bundle = args[0] if args else next(iter(kwargs.values()))

    # The assembler's assemble_criterion was called for this criterion.
    assert assembler_log.is_file()
    records = [
        json.loads(line)
        for line in assembler_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    crit_calls = [r for r in records if r["fn"] == "assemble_criterion"]
    assert crit_calls, "verify never called spec-bundle-assembler.assemble_criterion"
    matching = [
        r
        for r in crit_calls
        if r["args"][0] == COMPONENT_ID
        and r["args"][1] == CRITERION_ID
        and Path(r["args"][2]).resolve() == repo_root.resolve()
    ]
    assert matching, crit_calls

    # The bundle passed is exactly the assembler-produced CriterionBundle,
    # not one the orchestrator built itself.
    assert getattr(bundle, "FAKE_MARKER", None) == "fake-assembler-" + nonce
    for name, value in _expected_bundle_fields(nonce).items():
        assert field(bundle, name) == value, name

    # The returned test code was executed and produced the criterion's result.
    assert marker.is_file(), "returned test code was never executed"
    assert "ran" in marker.read_text(encoding="utf-8")

    criteria = field(report, "criteria")
    entries = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(entries) == 1
    entry = entries[0]
    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") == expected_result