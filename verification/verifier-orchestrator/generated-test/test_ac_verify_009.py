import json
import uuid
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"
COVERS = "R-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FAKE_ASSEMBLER_SOURCE = "\n".join([
    "import dataclasses",
    "import hashlib",
    "import json",
    "from pathlib import Path",
    "",
    "",
    "class _MappingMixin:",
    "    def keys(self):",
    "        return [f.name for f in dataclasses.fields(self)]",
    "",
    "    def __getitem__(self, key):",
    "        if key not in self.keys():",
    "            raise KeyError(key)",
    "        return getattr(self, key)",
    "",
    "    def get(self, key, default=None):",
    "        return getattr(self, key) if key in self.keys() else default",
    "",
    "    def __contains__(self, key):",
    "        return key in self.keys()",
    "",
    "    def __iter__(self):",
    "        return iter(self.keys())",
    "",
    "    def __len__(self):",
    "        return len(self.keys())",
    "",
    "",
    "@dataclasses.dataclass",
    "class CriterionBundle(_MappingMixin):",
    "    component_id: str",
    "    criterion_id: str",
    "    covers: str",
    "    criterion_text: str",
    "    requirement_text: str",
    "    interface: str",
    "    glossary: str",
    "    dependency_interfaces: dict = dataclasses.field(default_factory=dict)",
    "",
    "",
    "@dataclasses.dataclass",
    "class SpecBundle(_MappingMixin):",
    "    component_id: str",
    "    spec_bundle_hash: str",
    "    spec: str",
    "    interface: str",
    "    constraints: str",
    "    dependency_interfaces: dict = dataclasses.field(default_factory=dict)",
    "    dependency_context: dict = dataclasses.field(default_factory=dict)",
    "    dependency_usage: dict = dataclasses.field(default_factory=dict)",
    "    vars: dict = dataclasses.field(default_factory=dict)",
    "    glossary: str = ''",
    "    hint_code: object = None",
    "",
    "",
    "def _log(repo_root, record):",
    "    log_path = Path(repo_root) / 'assembler_calls.jsonl'",
    "    with open(log_path, 'a', encoding='utf-8') as fh:",
    "        fh.write(json.dumps(record) + '\\n')",
    "",
    "",
    "def _token(repo_root):",
    "    return (Path(repo_root) / 'sentinel_token.txt').read_text(encoding='utf-8').strip()",
    "",
    "",
    "def assemble_criterion(component_id, criterion_id, repo_root):",
    "    _log(repo_root, {'fn': 'assemble_criterion', 'component_id': component_id,",
    "                     'criterion_id': criterion_id, 'repo_root': str(repo_root)})",
    "    token = _token(repo_root)",
    "    return CriterionBundle(",
    "        component_id=component_id,",
    "        criterion_id=criterion_id,",
    "        covers='R-WIDGET-001',",
    "        criterion_text='SENTINEL ' + token + ' criterion text',",
    "        requirement_text='SENTINEL ' + token + ' requirement text',",
    "        interface='SENTINEL ' + token + ' interface text',",
    "        glossary='SENTINEL ' + token + ' glossary text',",
    "        dependency_interfaces={'comp-sentinel-dep': 'SENTINEL ' + token + ' dependency interface'},",
    "    )",
    "",
    "",
    "def assemble(component_id, repo_root, mode='cold'):",
    "    _log(repo_root, {'fn': 'assemble', 'component_id': component_id,",
    "                     'repo_root': str(repo_root), 'mode': mode})",
    "    root = Path(repo_root)",
    "    comp = root / 'specs' / 'components' / 'widget'",
    "    spec_text = (comp / 'component.md').read_text(encoding='utf-8')",
    "    for p in sorted((comp / 'requirements').glob('*.md')):",
    "        spec_text += '\\n\\n' + p.read_text(encoding='utf-8').strip()",
    "    iface = (comp / 'interface' / 'library.md').read_text(encoding='utf-8').strip()",
    "    constraints = (comp / 'constraints.md').read_text(encoding='utf-8').strip()",
    "    glossary = (root / 'specs' / 'glossary.md').read_text(encoding='utf-8').strip()",
    "    digest = hashlib.sha256((spec_text + iface + constraints + glossary).encode('utf-8')).hexdigest()",
    "    return SpecBundle(",
    "        component_id=component_id,",
    "        spec_bundle_hash='sha256:' + digest,",
    "        spec=spec_text,",
    "        interface=iface,",
    "        constraints=constraints,",
    "        glossary=glossary,",
    "        hint_code=None,",
    "    )",
    "",
])


def _build_fixture(repo_root: Path, token: str) -> None:
    _write(repo_root / "sentinel_token.txt", token + "\n")

    _write(repo_root / "specs" / "glossary.md", "\n".join([
        "# Glossary",
        "",
        "- **Widget term** — a test term.",
        "",
    ]))

    _write(repo_root / "specs" / "product" / "widgetry.md", "\n".join([
        "---",
        "id: P-WIDGETRY",
        "title: Widgetry",
        "status: draft",
        "owners: [team-a]",
        "---",
        "",
        "# Widgetry",
        "",
        "## Purpose",
        "",
        "Widgets double numbers.",
        "",
        "## Scope",
        "",
        "- In scope: doubling.",
        "",
        "## Capability scenarios",
        "",
        "### CS-WIDGETRY-001",
        "",
        "Covers: P-WIDGETRY",
        "Kind: llm-judge",
        "",
        "```gherkin",
        "Given a number",
        "When it is doubled",
        "Then the result is twice the number",
        "```",
        "",
    ]))

    comp = repo_root / "specs" / "components" / SLUG
    _write(comp / "component.md", "\n".join([
        "---",
        "id: comp-widget",
        "title: Widget",
        "status: draft",
        "owners: [team-a]",
        "depends_on: []",
        "realizes: [P-WIDGETRY]",
        "---",
        "",
        "# Widget",
        "",
        "## Purpose",
        "",
        "Widget doubles a number.",
        "",
        "## Scope",
        "",
        "- In scope: doubling an integer.",
        "- Out of scope: everything else.",
        "",
        "## Definitions",
        "",
        "None.",
        "",
        "## Behavior",
        "",
        "See `requirements/`.",
        "",
        "## Interfaces",
        "",
        "See `interface/`.",
        "",
        "## Data",
        "",
        "See `interface/data/`.",
        "",
        "## Acceptance criteria",
        "",
        "See `acceptance/`.",
        "",
        "## Non-functional constraints",
        "",
        "See `constraints.md`.",
        "",
        "## Open questions",
        "",
        "## Change log",
        "",
        "- Initial draft.",
        "",
    ]))

    _write(comp / "requirements" / "R-WIDGET-001.md", "\n".join([
        "# R-WIDGET-001",
        "",
        "**R-WIDGET-001** — `double_it(x)` MUST return `2 * x`.",
        "",
    ]))

    _write(comp / "acceptance" / "AC-WIDGET-001.md", "\n".join([
        "# AC-WIDGET-001",
        "",
        "Covers: R-WIDGET-001",
        "Kind: generated-test",
        "",
        "```gherkin",
        "Given a widget input of 2",
        "When double_it is called with that input",
        "Then it returns 4",
        "```",
        "",
    ]))

    _write(comp / "interface" / "library.md", "\n".join([
        "# Library",
        "",
        "```",
        "double_it(x: int) -> int",
        "```",
        "",
    ]))

    _write(comp / "constraints.md", "\n".join([
        "# Constraints",
        "",
        "None.",
        "",
    ]))

    _write(repo_root / "gen" / SLUG / "widget.py", "\n".join([
        "def double_it(x):",
        "    return 2 * x",
        "",
    ]))

    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        FAKE_ASSEMBLER_SOURCE,
    )


def _expected_bundle(token: str) -> dict:
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": COVERS,
        "criterion_text": "SENTINEL " + token + " criterion text",
        "requirement_text": "SENTINEL " + token + " requirement text",
        "interface": "SENTINEL " + token + " interface text",
        "glossary": "SENTINEL " + token + " glossary text",
        "dependency_interfaces": {
            "comp-sentinel-dep": "SENTINEL " + token + " dependency interface"
        },
    }


def _authored_test_code(marker: Path, passing: bool) -> str:
    lines = [
        "from pathlib import Path",
        "",
        "",
        "def test_ac_widget_001():",
        "    marker = Path(" + repr(str(marker)) + ")",
        "    with open(marker, 'a', encoding='utf-8') as fh:",
        "        fh.write('ran\\n')",
    ]
    if passing:
        lines.append("    assert True")
    else:
        lines.append("    assert False, 'authored test deliberately fails'")
    lines.append("")
    return "\n".join(lines)


def _run_scenario(tmp_path: Path, passing: bool):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    token = uuid.uuid4().hex
    _build_fixture(repo_root, token)

    # No cached test exists for the criterion.
    cached = repo_root / "verification" / SLUG / "generated-test" / "test_ac_widget_001.py"
    assert not cached.exists()

    marker = tmp_path / ("authored_test_ran_" + token + ".txt")
    code = _authored_test_code(marker, passing)
    received = []

    def fake_test_author(bundle):
        received.append(bundle)
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "mock-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": code,
            },
            "model_call_error": None,
        }

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=fake_test_author
    )
    return repo_root, token, marker, received, report


def _assert_dispatch_with_assembler_bundle(repo_root, token, received):
    # test_author invoked exactly once
    assert len(received) == 1, "test_author called %d times" % len(received)
    bundle = received[0]

    # ... with exactly the bundle spec-bundle-assembler.assemble_criterion returned
    expected = _expected_bundle(token)
    for name, value in expected.items():
        assert field(bundle, name) == value, (
            "CriterionBundle field %r differs from assembler's output" % name
        )

    # The assembler was actually asked for this criterion's bundle.
    log_path = repo_root / "assembler_calls.jsonl"
    assert log_path.is_file(), "spec-bundle-assembler.assemble_criterion was never called"
    calls = [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ac_calls = [c for c in calls if c["fn"] == "assemble_criterion"]
    assert ac_calls, "assemble_criterion was never called"
    for c in ac_calls:
        assert c["component_id"] == COMPONENT_ID
        assert c["criterion_id"] == CRITERION_ID
        assert Path(c["repo_root"]).resolve() == repo_root.resolve()


def _criterion_entry(report):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matches) == 1, "expected exactly one entry for %s" % CRITERION_ID
    return matches[0]


def test_generated_test_dispatches_assembler_bundle_and_runs_passing_code(tmp_path):
    repo_root, token, marker, received, report = _run_scenario(tmp_path, passing=True)

    _assert_dispatch_with_assembler_bundle(repo_root, token, received)

    # The returned test code was executed ...
    assert marker.is_file(), "the test code returned by test_author was never executed"
    assert "ran" in marker.read_text(encoding="utf-8")

    # ... and produced the criterion's result.
    entry = _criterion_entry(report)
    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") == "pass"


def test_generated_test_dispatches_assembler_bundle_and_runs_failing_code(tmp_path):
    repo_root, token, marker, received, report = _run_scenario(tmp_path, passing=False)

    _assert_dispatch_with_assembler_bundle(repo_root, token, received)

    # The returned test code was executed ...
    assert marker.is_file(), "the test code returned by test_author was never executed"
    assert "ran" in marker.read_text(encoding="utf-8")

    # ... and its failure determines the criterion's result.
    entry = _criterion_entry(report)
    assert field(entry, "kind") == "generated-test"
    assert field(entry, "result") == "fail"