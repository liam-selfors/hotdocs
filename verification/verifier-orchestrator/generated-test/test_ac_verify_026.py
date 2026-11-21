# hotdocs-criterion: sha256:a33cd3b425d66afecb472f957a83e71cc874a813e8a0afa74567dd79172dff1e
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


CRITERION_ID = "AC-QUX-001"
COMPONENT_ID = "comp-qux"

BUNDLE_TEXT = {
    "criterion_text": "Given a table asset\nWhen asset_runner is called\nThen it returns the entry's number",
    "requirement_text": "R-QUX-001: qux MUST provide data/table.txt mapping a to 1 and b to 2.",
    "interface": "# Library\n\n```\nqux() -> None\n```\n",
    "glossary": "# Glossary\n",
    "testing": "\n## Asset kind: fake\n\nFake test text.",
}


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def header_line():
    payload = json.dumps(
        {k: BUNDLE_TEXT[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def cached_test_source(entries):
    lines = [header_line(), "", "", "def test_table(asset_runner):"]
    for entry, value in entries:
        lines.append(
            "    assert asset_runner(" + repr("data/table.txt") + ")(" + repr(entry) + ", []) == " + repr(value)
        )
    return "\n".join(lines) + "\n"


def build_fixture(root, entries):
    log = root / "calls.log"
    # Product capability so the unsealed component's realizes resolves.
    write(
        root / "specs" / "product" / "qux.md",
        "---\nid: P-QUX\ntitle: Qux capability\nstatus: draft\nowners: [team]\n---\n\n"
        "# Qux capability\n\n## Purpose\n\nQux.\n\n## Scope\n\n- qux\n\n"
        "### CS-QUX-001\n\nCovers: P-QUX\n\n```gherkin\nGiven a qux is 1\nWhen qux is invoked with []\nThen result equals null\n```\n",
    )
    write(root / "specs" / "glossary.md", "# Glossary\n")
    comp = root / "specs" / "components" / "qux"
    write(
        comp / "component.md",
        "---\nid: comp-qux\ntitle: Qux\nstatus: draft\nowners: [team]\nrealizes: [P-QUX]\n"
        "assets: [fake:data/table.txt]\n---\n\n"
        "# Qux\n\n## Purpose\n\nProvides a table asset.\n\n## Scope\n\n- In scope: the table.\n\n"
        "## Definitions\n\nNone.\n\n## Behavior\n\nSee `requirements/`.\n\n## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n## Open questions\n\n## Change log\n\n- Initial.\n",
    )
    write(
        comp / "requirements" / "R-QUX-001.md",
        "**R-QUX-001** - qux MUST provide data/table.txt mapping a to 1 and b to 2.\n",
    )
    write(comp / "interface" / "library.md", "# Library\n\n```\nqux() -> None\n```\n")
    write(comp / "interface" / "assets" / "table.txt.md", "# table.txt\n\nEntries a and b.\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        comp / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n\nCovers: R-QUX-001\nKind: generated-test\n\n"
        "```gherkin\nGiven a table asset\nWhen asset_runner is called\nThen it returns the entry's number\n```\n",
    )

    # Fake asset kind definition.
    sections = [
        "Layout", "Environment", "Surface", "Running criteria",
        "Strength check", "Test author guidance", "Generator guidance",
    ]
    definition = "---\nid: arch-asset-kind-fake\ntitle: Asset kind fake\nstatus: draft\nowners: [team]\n---\n\n# Asset kind fake\n"
    for s in sections:
        definition += "\n## " + s + "\n\nFake " + s.lower() + ".\n"
    write(root / "specs" / "architecture" / "asset-kind-fake.md", definition)

    # Fake adapter.
    adapter = (
        "from pathlib import Path\n\n"
        "KIND = 'fake'\n\n\n"
        "class AssetError(Exception):\n    pass\n\n\n"
        "def layout_errors(asset_file):\n    return []\n\n\n"
        "def surface(asset_file):\n    return dict(names=[])\n\n\n"
        "def guidance():\n    return dict(generator='Fake generator text.', test_author='Fake test text.')\n\n\n"
        "def provision(repo_root):\n"
        "    return dict(ok=True, reason='', versions=dict(fake='1.0'), lockfile_sha256=None, interpreter=None)\n\n\n"
        "def asset_runner(asset_file):\n"
        "    asset_file = Path(asset_file)\n"
        "    def run(entry, args):\n"
        "        for line in asset_file.read_text().splitlines():\n"
        "            key, _, value = line.partition('=')\n"
        "            if key == entry:\n"
        "                return int(value)\n"
        "        raise AssetError('no entry ' + entry)\n"
        "    return run\n\n\n"
        "def strength_sites(asset_file):\n"
        "    return [dict(description='1: a'), dict(description='2: b')]\n\n\n"
        "def apply_site(asset_file, site):\n"
        "    asset_file = Path(asset_file)\n"
        "    n = int(site['description'].split(':')[0]) - 1\n"
        "    lines = asset_file.read_text().splitlines()\n"
        "    key, _, value = lines[n].partition('=')\n"
        "    lines[n] = key + '=' + str(int(value) + 1)\n"
        "    asset_file.write_text('\\n'.join(lines) + '\\n')\n"
    )
    write(root / "gen" / "kind-fake" / "kind_fake.py", adapter)

    # Component code and asset.
    write(root / "gen" / "qux" / "qux.py", "def qux():\n    return None\n")
    write(root / "gen" / "qux" / "data" / "table.txt", "a=1\nb=2\n")

    # spec-bundle-assembler stand-in.
    bundle = {
        "component_id": COMPONENT_ID,
        "criterion_id": CRITERION_ID,
        "covers": "R-QUX-001",
        "criterion_text": BUNDLE_TEXT["criterion_text"],
        "requirement_text": BUNDLE_TEXT["requirement_text"],
        "interface": BUNDLE_TEXT["interface"],
        "glossary": BUNDLE_TEXT["glossary"],
        "dependency_interfaces": {},
        "testing": BUNDLE_TEXT["testing"],
    }
    write(
        root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(bundle) + "\n\n\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    b = dict(BUNDLE)\n"
        "    b['component_id'] = component_id\n"
        "    b['criterion_id'] = criterion_id\n"
        "    return b\n",
    )

    # test-probe stand-in.
    write(
        root / "gen" / "test-probe" / "test_probe.py",
        "class ProbeReport:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 1\n"
        "        self.tests_reached = 1\n\n"
        "    def to_dict(self):\n"
        "        return dict(ok=self.ok, findings=list(self.findings), tests_run=self.tests_run, tests_reached=self.tests_reached)\n\n\n"
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    with open(" + repr(str(log)) + ", 'a') as f:\n"
        "        f.write('probe\\n')\n"
        "    return ProbeReport()\n",
    )

    # Cached generated test with a correct header.
    source = cached_test_source(entries)
    write(root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py", source)

    def test_author(bundle_arg):
        with open(log, "a") as f:
            f.write("test_author\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {"path": "verification/qux/generated-test/test_ac_qux_001.py", "content": source},
        }

    return test_author


def criterion_of(report, criterion_id):
    for c in field(report, "criteria"):
        if field(c, "id") == criterion_id:
            return c
    raise AssertionError("criterion " + criterion_id + " missing from report")


def run_verify(root, entries):
    author = build_fixture(root, entries)
    return verifier_orchestrator.verify(COMPONENT_ID, root, judge=None, test_author=author)


def test_one_asset_assertion_scores_half(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    report = run_verify(root, [("a", 1)])
    c = criterion_of(report, CRITERION_ID)
    assert field(c, "result") == "pass"
    assert field(report, "mutation_score") == 0.5
    assert field(report, "overall") == "fail"


def test_both_asset_assertions_score_full(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    report = run_verify(root, [("a", 1), ("b", 2)])
    assert field(report, "mutation_score") == 1.0