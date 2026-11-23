# hotdocs-criterion: sha256:3cf02c6980738a165f0c8c0ba334bd26a9924d3ea4b8a0182466e97e9713542b
import json
import uuid
from collections.abc import Mapping
from pathlib import Path

import verifier_orchestrator


COMPONENT_ID = "comp-widget"
SLUG = "widget"
CRITERION_ID = "AC-WIDGET-001"
REQ_ID = "R-WIDGET-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def expected_bundle(nonce):
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQ_ID,
        "criterion_text": "Fake criterion text " + nonce,
        "requirement_text": "Fake requirement text " + nonce,
        "interface": "make_widget(x) -> int " + nonce,
        "glossary": "Fake glossary " + nonce,
        "dependency_interfaces": {"comp-other": "other_get(key) -> str " + nonce},
        "testing": "Fake testing " + nonce,
    }


def build_fixture(repo_root, nonce, assembler_log, ):
    comp_dir = repo_root / "specs" / "components" / SLUG
    write(
        comp_dir / "component.md",
        "---\n"
        "id: comp-widget\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Makes widgets.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: widgets.\n"
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
        "- Initial.\n",
    )
    write(
        comp_dir / "requirements" / (REQ_ID + ".md"),
        "# " + REQ_ID + "\n\n**" + REQ_ID + "** - `make_widget(x)` MUST return `x + 1`.\n",
    )
    write(
        comp_dir / "interface" / "library.md",
        "# Library\n\n```\nmake_widget(x: int) -> int\n```\n",
    )
    write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp_dir / "acceptance" / (CRITERION_ID + ".md"),
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQ_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget input of 1\n"
        "When make_widget is called with it\n"
        "Then it returns 2\n"
        "```\n",
    )
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widgets\n"
        "status: draft\n"
        "owners: [team]\n"
        "---\n"
        "\n"
        "# Widgets\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Widgets.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    write(
        repo_root / "gen" / SLUG / "widget.py",
        "def make_widget(x):\n    return x + 1\n",
    )

    bundle = expected_bundle(nonce)
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "import json\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    with open(" + repr(str(assembler_log)) + ", 'a', encoding='utf-8') as f:\n"
        "        f.write(json.dumps({'component_id': component_id, 'criterion_id': criterion_id, 'repo_root': str(repo_root)}) + '\\n')\n"
        "    return json.loads(" + repr(json.dumps(bundle)) + ")\n",
    )
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "class _Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings), 'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None, assets=None):\n"
        "    return _Report()\n",
    )
    return bundle


def bundle_view(bundle, keys):
    out = {}
    for k in keys:
        if isinstance(bundle, Mapping):
            out[k] = bundle[k]
        else:
            out[k] = getattr(bundle, k)
    return out


def make_test_author(author_log, expected_keys, test_code):
    def test_author_stub(bundle):
        view = bundle_view(bundle, expected_keys)
        extra = None
        if isinstance(bundle, Mapping):
            extra = sorted(bundle.keys())
        with open(author_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"bundle": view, "keys": extra}) + "\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "mock-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/widget/generated-test/test_ac_widget_001.py",
                "content": test_code,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return test_author_stub


def generated_code(marker, passes):
    return (
        "def test_widget_marker():\n"
        "    with open(" + repr(str(marker)) + ", 'a', encoding='utf-8') as f:\n"
        "        f.write('ran\\n')\n"
        "    assert " + ("True" if passes else "False") + "\n"
    )


def run_scenario(tmp_path, passes):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    assembler_log = logs / "assembler.log"
    author_log = logs / "author.log"
    marker = logs / "marker.log"
    nonce = uuid.uuid4().hex

    bundle = build_fixture(repo_root, nonce, assembler_log)
    cached = repo_root / "verification" / SLUG / "generated-test" / "test_ac_widget_001.py"
    assert not cached.exists()

    keys = list(bundle.keys())
    author = make_test_author(author_log, keys, generated_code(marker, passes))

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root, test_author=author)

    # test_author invoked once, with exactly the assembler's bundle
    assert author_log.exists(), "test_author was never invoked"
    calls = [json.loads(line) for line in author_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(calls) == 1
    assert calls[0]["bundle"] == bundle
    if calls[0]["keys"] is not None:
        assert calls[0]["keys"] == sorted(keys)

    # the bundle came from assemble_criterion for this criterion
    assert assembler_log.exists(), "assemble_criterion was never called"
    asm_calls = [json.loads(line) for line in assembler_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(
        c["component_id"] == COMPONENT_ID and c["criterion_id"] == CRITERION_ID
        for c in asm_calls
    )

    # the returned test code was executed
    assert marker.exists(), "returned test code was never executed"
    assert "ran" in marker.read_text(encoding="utf-8").splitlines()

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1
    return matching[0]


def test_ac_verify_009_returned_passing_code_gives_pass(tmp_path):
    crit = run_scenario(tmp_path, passes=True)
    assert field(crit, "result") == "pass"


def test_ac_verify_009_returned_failing_code_gives_fail(tmp_path):
    crit = run_scenario(tmp_path, passes=False)
    assert field(crit, "result") == "fail"