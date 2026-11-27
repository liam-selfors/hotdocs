# hotdocs-criterion: sha256:ac9f85bc693366e4e5d453ce87720275e99635b6b922d63e3eb3e7efe5c8b549
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


SLUG = "widget"
COMPONENT_ID = "comp-widget"
CRITERION_ID = "AC-WIDGET-001"
REQUIREMENT_ID = "R-WIDGET-001"
TEST_FILENAME = "test_ac_widget_001.py"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def criterion_text():
    return (
        "# " + CRITERION_ID + "\n"
        "\n"
        "Covers: " + REQUIREMENT_ID + "\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a widget module exists\n"
        "When its generated test runs\n"
        "Then a marker file is written\n"
        "```\n"
    )


def requirement_text():
    return (
        "# " + REQUIREMENT_ID + "\n"
        "\n"
        "**" + REQUIREMENT_ID + "** - The widget component MUST exist so its\n"
        "generated test can run against it.\n"
    )


def interface_text():
    return (
        "# Library\n"
        "\n"
        "The importable module is `widget`; it declares no functions.\n"
    )


def build_bundle():
    return {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": REQUIREMENT_ID,
        "criterion_text": criterion_text(),
        "requirement_text": requirement_text(),
        "interface": interface_text(),
        "glossary": "# Glossary\n\n- **Widget** - a fixture thing.\n",
        "dependency_interfaces": {},
        "testing": "",
    }


def header_for(bundle):
    keys = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    payload = json.dumps(
        {k: bundle[k] for k in keys},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return "# hotdocs-criterion: sha256:" + digest


def build_fixture(repo_root):
    bundle = build_bundle()

    write(
        repo_root / "specs" / "components" / SLUG / "component.md",
        "---\n"
        "id: " + COMPONENT_ID + "\n"
        "title: Widget\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "depends_on: []\n"
        "realizes: [P-WIDGET]\n"
        "---\n"
        "# Widget\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A fixture component for verification.\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "requirements" / (REQUIREMENT_ID + ".md"),
        requirement_text(),
    )
    write(
        repo_root / "specs" / "components" / SLUG / "acceptance" / (CRITERION_ID + ".md"),
        criterion_text(),
    )
    write(
        repo_root / "specs" / "components" / SLUG / "interface" / "library.md",
        interface_text(),
    )
    write(
        repo_root / "specs" / "components" / SLUG / "constraints.md",
        "# Constraints\n\nNone.\n",
    )
    write(
        repo_root / "specs" / "product" / "widget.md",
        "---\n"
        "id: P-WIDGET\n"
        "title: Widget capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "# Widget capability\n"
        "\n"
        "A fixture capability.\n",
    )
    write(repo_root / "specs" / "glossary.md", bundle["glossary"])

    # Code under test: an empty module, since the test imports nothing from it.
    write(repo_root / "gen" / SLUG / (SLUG + ".py"), "")

    # spec-bundle-assembler stand-in.
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(bundle) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )

    # test-probe stand-in: always ok, no findings.
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
        "class _ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings)}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    return _ProbeReport()\n",
    )

    # Current cached generated test, with the correct header, which writes a marker.
    marker = (repo_root / "marker.txt").resolve()
    write(
        repo_root / "verification" / SLUG / "generated-test" / TEST_FILENAME,
        header_for(bundle) + "\n"
        "from pathlib import Path\n"
        "\n"
        "\n"
        "def test_writes_marker():\n"
        "    Path(" + repr(str(marker)) + ").write_text('ran', encoding='utf-8')\n"
        "    assert True\n",
    )
    return marker


def test_cached_generated_test_runs_and_passes(tmp_path):
    repo_root = tmp_path.resolve()
    marker = build_fixture(repo_root)
    assert not marker.exists()

    report = verifier_orchestrator.verify(COMPONENT_ID, repo_root)

    assert marker.exists()

    criteria = field(report, "criteria")
    matching = [c for c in criteria if field(c, "id") == CRITERION_ID]
    assert len(matching) == 1, criteria
    entry = matching[0]
    assert field(entry, "result") == "pass", entry