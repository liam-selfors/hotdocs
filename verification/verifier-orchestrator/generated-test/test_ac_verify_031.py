# hotdocs-criterion: sha256:de96f8e30030ff36e8fa1ad3b5a1fbc1ffd013b6a4c6534bb3aa6848ff737ee8
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import verifier_orchestrator


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def sha_of(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


BUNDLE = {
    "component_id": "comp-qux",
    "criterion_id": "AC-QUX-001",
    "covers": "R-QUX-001",
    "criterion_text": "Given a qux table\nWhen qux_read is invoked\nThen the result is 1",
    "requirement_text": "R-QUX-001 qux_read MUST return 1.",
    "interface": "# Library\n\nqux_read(entry: str) -> int",
    "glossary": "# Glossary",
    "dependency_interfaces": {},
    "testing": "",
}


def header_line():
    payload = json.dumps(
        {k: BUNDLE[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def passing_test_source():
    return header_line() + "\n" + "def test_passes():\n    assert 1 == 1\n"


FAKE_ADAPTER = (
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
    "    asset_file = Path(asset_file)\n"
    "\n"
    "    def run(entry, args):\n"
    "        for line in asset_file.read_text().splitlines():\n"
    "            if line.startswith(entry + '='):\n"
    "                return int(line[len(entry) + 1:])\n"
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
    "    asset_file = Path(asset_file)\n"
    "    index = int(site['description'].split(':')[0]) - 1\n"
    "    lines = asset_file.read_text().splitlines()\n"
    "    key, value = lines[index].split('=', 1)\n"
    "    lines[index] = key + '=' + str(int(value) + 1)\n"
    "    asset_file.write_text('\\n'.join(lines) + '\\n')\n"
)


FAKE_KIND_DEFINITION = (
    "---\n"
    "id: arch-asset-kind-fake\n"
    "title: Asset kind fake\n"
    "status: draft\n"
    "owners: [test-team]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Asset kind fake\n"
    "\n"
    "## Layout\n\nA text file of key=value lines.\n\n"
    "## Environment\n\nNo programs.\n\n"
    "## Surface\n\nNo names.\n\n"
    "## Running criteria\n\nasset_runner takes an entry and returns its integer.\n\n"
    "## Strength check\n\nmutation: each line's number plus one.\n\n"
    "## Test author guidance\n\nFake test text.\n\n"
    "## Generator guidance\n\nFake generator text.\n"
)


def build_fixture(repo_root, with_assets):
    repo_root = Path(repo_root)
    assets_line = "assets: [fake:data/table.txt]\n" if with_assets else ""
    write(
        repo_root / "specs" / "components" / "qux" / "component.md",
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "realizes: [P-QUX]\n"
        + assets_line
        + "---\n"
        "\n"
        "# Qux\n\n"
        "## Purpose\n\nReads a qux table.\n\n"
        "## Scope\n\n- In scope: reading.\n\n"
        "## Definitions\n\nNone.\n\n"
        "## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n"
        "## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n"
        "## Change log\n\n- Initial.\n",
    )
    write(
        repo_root / "specs" / "components" / "qux" / "requirements" / "R-QUX-001.md",
        "**R-QUX-001** - qux_read MUST return 1.\n",
    )
    write(
        repo_root / "specs" / "components" / "qux" / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a qux table\n"
        "When qux_read is invoked\n"
        "Then the result is 1\n"
        "```\n",
    )
    write(
        repo_root / "specs" / "components" / "qux" / "interface" / "library.md",
        "# Library\n\n```\nqux_read(entry: str) -> int\n```\n",
    )
    write(repo_root / "specs" / "components" / "qux" / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [test-team]\n"
        "---\n"
        "\n"
        "# Qux capability\n\n## Purpose\n\nQux.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    write(repo_root / "gen" / "qux" / "qux.py", "")
    if with_assets:
        write(repo_root / "gen" / "qux" / "data" / "table.txt", "a=1\nb=2\n")
        write(repo_root / "specs" / "architecture" / "asset-kind-fake.md", FAKE_KIND_DEFINITION)
        write(repo_root / "gen" / "kind-fake" / "kind_fake.py", FAKE_ADAPTER)

    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        "BUNDLE = " + repr(BUNDLE) + "\n"
        "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    return dict(BUNDLE)\n",
    )
    write(
        repo_root / "gen" / "test-probe" / "test_probe.py",
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
        "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
        "    return ProbeReport()\n",
    )
    write(
        repo_root / "verification" / "qux" / "generated-test" / "test_ac_qux_001.py",
        passing_test_source(),
    )
    return repo_root


def make_test_author(log_path):
    def test_author(bundle):
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write("called\n")
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

    return test_author


def python_entry(repo_root):
    adapter_path = Path(verifier_orchestrator.__file__).parents[1] / "kind-python" / "kind_python.py"
    kind_python = load_module(adapter_path, "kind_python")
    versions = kind_python.provision(repo_root)["versions"]
    return {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": sha_of(adapter_path),
        "versions": versions,
        "lockfile_sha256": None,
    }


def test_assets_report_python_then_declared_fake(tmp_path):
    repo_root = build_fixture(tmp_path / "repo", with_assets=True)
    log_path = tmp_path / "author.log"
    expected_python = python_entry(repo_root)
    definition = "sha256:" + hashlib.sha256(
        (repo_root / "specs" / "architecture" / "asset-kind-fake.md").read_bytes()
    ).hexdigest()
    adapter = "sha256:" + hashlib.sha256(
        (repo_root / "gen" / "kind-fake" / "kind_fake.py").read_bytes()
    ).hexdigest()

    report = verifier_orchestrator.verify(
        "comp-qux", repo_root, judge=None, test_author=make_test_author(log_path)
    )

    assets = field(report, "assets")
    assert list(assets) == [
        expected_python,
        {
            "kind": "fake",
            "path": "data/table.txt",
            "definition_sha256": definition,
            "adapter_sha256": adapter,
            "versions": {"fake": "1.0"},
            "lockfile_sha256": None,
        },
    ]


def test_assets_report_only_python_without_declared_assets(tmp_path):
    repo_root = build_fixture(tmp_path / "repo", with_assets=False)
    log_path = tmp_path / "author.log"
    expected_python = python_entry(repo_root)

    report = verifier_orchestrator.verify(
        "comp-qux", repo_root, judge=None, test_author=make_test_author(log_path)
    )

    assets = field(report, "assets")
    assert list(assets) == [expected_python]