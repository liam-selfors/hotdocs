# hotdocs-criterion: sha256:c49e4f07eea626e934701d5b1b31bda67ee84c65f080bdd0fa9daebe23bbbc72
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import verifier_orchestrator


FIVE_KEYS = ("criterion_text", "requirement_text", "interface", "glossary", "testing")

BUNDLE = {
    "component_id": "comp-qux",
    "criterion_id": "AC-QUX-001",
    "covers": "R-QUX-001",
    "criterion_text": "Given a qux value is 1 When qux runs Then it passes",
    "requirement_text": "R-QUX-001 - The component MUST exist.",
    "interface": "# Library\n\nqux_value() -> int\n",
    "glossary": "# Glossary\n",
    "dependency_interfaces": {},
    "testing": "",
}


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def as_plain(entry):
    if isinstance(entry, dict):
        return entry
    if hasattr(entry, "to_dict"):
        return entry.to_dict()
    return dict(vars(entry))


def file_sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def header_line():
    payload = json.dumps(
        {k: BUNDLE[k] for k in FIVE_KEYS},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def passing_test_source():
    return header_line() + "\n\n\ndef test_qux_passes():\n    assert 1 + 1 == 2\n"


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


ASSEMBLER_SOURCE_TAIL = (
    "\n\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    bundle = dict(BUNDLE)\n"
    "    bundle['component_id'] = component_id\n"
    "    bundle['criterion_id'] = criterion_id\n"
    "    return bundle\n"
)

PROBE_SOURCE = (
    "class ProbeReport:\n"
    "    def __init__(self):\n"
    "        self.ok = True\n"
    "        self.findings = []\n"
    "        self.tests_run = 1\n"
    "        self.tests_reached = 1\n"
    "\n"
    "    def to_dict(self):\n"
    "        return {'ok': self.ok, 'findings': list(self.findings),\n"
    "                'tests_run': self.tests_run, 'tests_reached': self.tests_reached}\n"
    "\n"
    "\n"
    "GATE_VERSION = 'test-probe@1.4.0'\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0,\n"
    "          interpreter=None, assets=None):\n"
    "    return ProbeReport()\n"
)

FAKE_ADAPTER_SOURCE = (
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
    "    def run(entry, args):\n"
    "        for line in Path(asset_file).read_text().splitlines():\n"
    "            key, _, value = line.partition('=')\n"
    "            if key == entry:\n"
    "                return int(value)\n"
    "        raise KeyError(entry)\n"
    "    return run\n"
    "\n"
    "\n"
    "def strength_sites(asset_file):\n"
    "    return [{'description': '1: a'}, {'description': '2: b'}]\n"
    "\n"
    "\n"
    "def apply_site(asset_file, site):\n"
    "    number = int(site['description'].split(':')[0])\n"
    "    lines = Path(asset_file).read_text().splitlines()\n"
    "    key, _, value = lines[number - 1].partition('=')\n"
    "    lines[number - 1] = key + '=' + str(int(value) + 1)\n"
    "    Path(asset_file).write_text('\\n'.join(lines) + '\\n')\n"
)

FAKE_DEFINITION = (
    "---\n"
    "id: arch-asset-kind-fake\n"
    "title: Asset kind fake\n"
    "status: draft\n"
    "owners: [pipeline-team]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Asset kind `fake`\n"
    "\n"
    "## Layout\n\nA text file of key=value lines.\n\n"
    "## Environment\n\nNo programs are needed.\n\n"
    "## Surface\n\nNo names are provided.\n\n"
    "## Running criteria\n\nThe runner takes a key and returns its integer.\n\n"
    "## Strength check\n\nMutation of each line's number.\n\n"
    "## Test author guidance\n\nFake test text.\n\n"
    "## Generator guidance\n\nFake generator text.\n"
)


def build_fixture(repo_root, with_assets):
    repo_root = Path(repo_root)
    frontmatter = (
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [team]\n"
        "realizes: [P-QUX]\n"
    )
    if with_assets:
        frontmatter += "assets: [fake:data/table.txt]\n"
    frontmatter += "---\n"
    write(
        repo_root / "specs/components/qux/component.md",
        frontmatter
        + "\n# Qux\n\n## Purpose\n\nA fixture component.\n\n"
        "## Scope\n\n- In scope: nothing.\n\n## Definitions\n\nNone.\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n## Change log\n\n- Initial.\n",
    )
    write(
        repo_root / "specs/components/qux/requirements/R-QUX-001.md",
        "# R-QUX-001\n\n**R-QUX-001** - The component MUST exist.\n",
    )
    write(
        repo_root / "specs/components/qux/acceptance/AC-QUX-001.md",
        "# AC-QUX-001\n\nCovers: R-QUX-001\nKind: generated-test\n\n"
        "```gherkin\nGiven a qux value is 1\nWhen qux runs\nThen it passes\n```\n",
    )
    write(
        repo_root / "specs/components/qux/interface/library.md",
        "# Library\n\n```\nqux_value() -> int\n```\n",
    )
    write(repo_root / "specs/components/qux/constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs/product/P-QUX.md",
        "---\nid: P-QUX\ntitle: Qux capability\nstatus: draft\nowners: [team]\n---\n\n"
        "# Qux capability\n\n## Purpose\n\nFixture.\n\n## Scope\n\n- Fixture.\n\n"
        "### CS-QUX-001\n\nCovers: P-QUX\nKind: llm-judge\n\n"
        "```gherkin\nGiven a qux\nWhen it runs\nThen it works\n```\n",
    )
    write(repo_root / "specs/glossary.md", "# Glossary\n")

    write(repo_root / "specs/architecture/asset-kind-fake.md", FAKE_DEFINITION)
    write(repo_root / "gen/kind-fake/kind_fake.py", FAKE_ADAPTER_SOURCE)

    write(repo_root / "gen/qux/qux.py", "")
    if with_assets:
        write(repo_root / "gen/qux/data/table.txt", "a=1\nb=2\n")

    write(
        repo_root / "gen/spec-bundle-assembler/spec_bundle_assembler.py",
        "BUNDLE = " + repr(BUNDLE) + "\n" + ASSEMBLER_SOURCE_TAIL,
    )
    write(repo_root / "gen/test-probe/test_probe.py", PROBE_SOURCE)

    write(
        repo_root / "verification/qux/generated-test/test_ac_qux_001.py",
        passing_test_source(),
    )
    return repo_root


def make_author(log_path):
    def author(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "model_call_error": None,
            "file": {
                "path": "verification/qux/generated-test/test_ac_qux_001.py",
                "content": passing_test_source(),
            },
        }

    return author


def tool_python_adapter():
    gen = next(
        p for p in Path(verifier_orchestrator.__file__).resolve().parents if p.name == "gen"
    )
    return gen / "kind-python" / "kind_python.py"


def python_entry(repo_root):
    adapter = tool_python_adapter()
    module = load_module(adapter, "kind_python_ac_verify_031")
    versions = module.provision(Path(repo_root))["versions"]
    return {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": file_sha(adapter),
        "versions": versions,
        "lockfile_sha256": None,
    }


def run_verify(repo_root, tmp_path):
    log = tmp_path / "author.log"
    report = verifier_orchestrator.verify(
        "comp-qux", Path(repo_root), judge=None, test_author=make_author(log)
    )
    return report


def test_assets_with_declared_fake_asset(tmp_path):
    repo_root = build_fixture(tmp_path / "repo", with_assets=True)
    p_entry = python_entry(repo_root)
    d = file_sha(repo_root / "specs/architecture/asset-kind-fake.md")
    a = file_sha(repo_root / "gen/kind-fake/kind_fake.py")

    report = run_verify(repo_root, tmp_path)
    assets = [as_plain(e) for e in field(report, "assets")]

    assert assets == [
        p_entry,
        {
            "kind": "fake",
            "path": "data/table.txt",
            "definition_sha256": d,
            "adapter_sha256": a,
            "versions": {"fake": "1.0"},
            "lockfile_sha256": None,
        },
    ]


def test_assets_with_no_declared_assets(tmp_path):
    repo_root = build_fixture(tmp_path / "repo", with_assets=False)
    p_entry = python_entry(repo_root)

    report = run_verify(repo_root, tmp_path)
    assets = [as_plain(e) for e in field(report, "assets")]

    assert assets == [p_entry]