# hotdocs-criterion: sha256:4da913d17f7319918811253887cd0b6aa7227d4ffc97c7278ca02b0a2a6d99fc
import hashlib
import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


COMPONENT_MD = (
    "---\n"
    "id: comp-qux\n"
    "title: Qux\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "realizes: [P-QUX]\n"
    "assets: [fake:data/table.txt]\n"
    "---\n"
    "\n"
    "# Qux\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Qux holds a small lookup table asset.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: the table.\n"
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
    "- Initial.\n"
)

PRODUCT_MD = (
    "---\n"
    "id: P-QUX\n"
    "title: Qux capability\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Qux capability\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Provide a table.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- The table.\n"
)

REQUIREMENT_MD = (
    "# R-QUX-001\n"
    "\n"
    "**R-QUX-001** - The table asset MUST map b to 2.\n"
)

ACCEPTANCE_MD = (
    "# AC-QUX-001\n"
    "\n"
    "Covers: R-QUX-001\n"
    "Kind: generated-test\n"
    "\n"
    "```gherkin\n"
    "Given the table asset\n"
    "When entry b is read\n"
    "Then it is 2\n"
    "```\n"
)

KIND_DEF_MD = (
    "---\n"
    "id: arch-asset-kind-fake\n"
    "title: Asset kind fake\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Asset kind fake\n"
    "\n"
    "## Layout\n"
    "\n"
    "Lines of key=value.\n"
    "\n"
    "## Environment\n"
    "\n"
    "No programs.\n"
    "\n"
    "## Surface\n"
    "\n"
    "No names.\n"
    "\n"
    "## Running criteria\n"
    "\n"
    "run(entry, args) returns the integer for entry.\n"
    "\n"
    "## Strength check\n"
    "\n"
    "Mutation of each line's number.\n"
    "\n"
    "## Test author guidance\n"
    "\n"
    "Fake test text.\n"
    "\n"
    "## Generator guidance\n"
    "\n"
    "Fake generator text.\n"
)

KIND_FAKE_PY = (
    "from pathlib import Path\n"
    "\n"
    "KIND = 'fake'\n"
    "\n"
    "\n"
    "def layout_errors(asset_file):\n"
    "    return []\n"
    "\n"
    "\n"
    "def surface(asset_file):\n"
    "    return {'names': []}\n"
    "\n"
    "\n"
    "def guidance():\n"
    "    return {'generator': 'Fake generator text.', 'test_author': 'Fake test text.'}\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {'ok': True, 'reason': '', 'versions': {'fake': '1.0'}, 'lockfile_sha256': None}\n"
    "\n"
    "\n"
    "def asset_runner(asset_file):\n"
    "    path = Path(asset_file)\n"
    "\n"
    "    def run(entry, args):\n"
    "        for line in path.read_text().splitlines():\n"
    "            key, _, value = line.partition('=')\n"
    "            if key == entry:\n"
    "                return int(value)\n"
    "        raise KeyError(entry)\n"
    "\n"
    "    return run\n"
    "\n"
    "\n"
    "def strength_sites(asset_file):\n"
    "    return [{'description': '1: a'}, {'description': '2: b'}]\n"
    "\n"
    "\n"
    "def apply_site(asset_file, site):\n"
    "    path = Path(asset_file)\n"
    "    index = int(site['description'].split(':')[0]) - 1\n"
    "    lines = path.read_text().splitlines()\n"
    "    key, _, value = lines[index].partition('=')\n"
    "    lines[index] = key + '=' + str(int(value) + 1)\n"
    "    path.write_text('\\n'.join(lines) + '\\n')\n"
)

CACHED_TEST_BODY = (
    "import pytest\n"
    "\n"
    "\n"
    "def test_table_asset(asset_runner):\n"
    "    assert asset_runner('data/table.txt')('b', []) == 2\n"
    "    with pytest.raises(KeyError):\n"
    "        asset_runner('data/other.txt')\n"
)


def make_bundle():
    return {
        "component_id": "comp-qux",
        "criterion_id": "AC-QUX-001",
        "covers": "R-QUX-001",
        "criterion_text": ACCEPTANCE_MD,
        "requirement_text": REQUIREMENT_MD,
        "interface": "Qux interface text.",
        "glossary": "Qux glossary text.",
        "dependency_interfaces": {},
        "testing": "\n## Asset kind: fake\n\nFake test text.",
    }


def header_for(bundle):
    payload = json.dumps(
        {k: bundle[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def build_fixture(repo_root):
    comp = repo_root / "specs" / "components" / "qux"
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-QUX-001.md", REQUIREMENT_MD)
    write(comp / "acceptance" / "AC-QUX-001.md", ACCEPTANCE_MD)
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(comp / "interface" / "assets" / "table.txt.md", "# table.txt\n\nEntries a and b.\n")
    write(repo_root / "specs" / "product" / "qux.md", PRODUCT_MD)
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")
    write(repo_root / "specs" / "architecture" / "asset-kind-fake.md", KIND_DEF_MD)

    write(repo_root / "gen" / "qux" / "qux.py", "")
    write(repo_root / "gen" / "qux" / "data" / "table.txt", "a=1\nb=2\n")
    write(repo_root / "gen" / "kind-fake" / "kind_fake.py", KIND_FAKE_PY)

    bundle = make_bundle()
    assembler_src = (
        "BUNDLE = " + repr(bundle) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n"
    )
    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", assembler_src)

    probe_log = repo_root / "probe_calls.log"
    probe_src = (
        "import json\n"
        "\n"
        "LOG = " + repr(str(probe_log)) + "\n"
        "\n"
        "\n"
        "class Report:\n"
        "    def __init__(self):\n"
        "        self.ok = True\n"
        "        self.findings = []\n"
        "        self.tests_run = 0\n"
        "        self.tests_reached = 0\n"
        "\n"
        "    def to_dict(self):\n"
        "        return {'ok': self.ok, 'findings': list(self.findings),\n"
        "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
        "\n"
        "\n"
        "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
        "    with open(LOG, 'a') as handle:\n"
        "        handle.write(json.dumps(kwargs, default=str, sort_keys=True) + '\\n')\n"
        "    return Report()\n"
    )
    write(repo_root / "gen" / "test-probe" / "test_probe.py", probe_src)

    cached = repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py"
    content = header_for(bundle) + "\n" + CACHED_TEST_BODY
    write(cached, content)

    author_log = repo_root / "author_calls.log"

    def test_author_stub(b):
        with open(author_log, "a") as handle:
            handle.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {"path": "ignored.py", "content": content},
        }

    return test_author_stub, probe_log


def find_criterion(report, criterion_id):
    for c in field(report, "criteria"):
        if field(c, "id") == criterion_id:
            return c
    raise AssertionError("criterion " + criterion_id + " not in report")


def test_asset_criterion_passes(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    author, _ = build_fixture(repo_root)
    report = verifier_orchestrator.verify("comp-qux", repo_root, judge=None, test_author=author)
    crit = find_criterion(report, "AC-QUX-001")
    assert field(crit, "result") == "pass", crit


def test_probe_receives_declared_assets(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    author, probe_log = build_fixture(repo_root)
    verifier_orchestrator.verify("comp-qux", repo_root, judge=None, test_author=author)
    assert probe_log.is_file(), "test-probe stand-in was never called"
    records = [json.loads(line) for line in probe_log.read_text().splitlines() if line.strip()]
    assert len(records) >= 1
    for rec in records:
        assert "assets" in rec, rec
        assert rec["assets"] == ["data/table.txt"], rec