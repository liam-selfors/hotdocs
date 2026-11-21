# hotdocs-criterion: sha256:a2d5f73cb1141ccf700ff9f79b7c64e2db0af4123ace36ef618a26475c7e41e4
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import verifier_orchestrator


SLUG = "qux"
COMPONENT_ID = "comp-qux"
CRITERION_ID = "AC-QUX-001"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def sha256_of_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def tool_gen_dir():
    return next(
        p for p in Path(verifier_orchestrator.__file__).resolve().parents
        if p.name == "gen"
    )


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


BUNDLE = {
    "component_id": COMPONENT_ID,
    "criterion_id": CRITERION_ID,
    "covers": "R-QUX-001",
    "criterion_text": "Given a table\nWhen it is read\nThen it works",
    "requirement_text": "R-QUX-001 The component MUST work.",
    "interface": "# Library\n\nqux_read() -> int",
    "glossary": "# Glossary",
    "dependency_interfaces": {},
    "testing": "",
}


def criterion_header():
    payload = {k: BUNDLE[k] for k in ("criterion_text", "requirement_text", "interface", "glossary", "testing")}
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


PASSING_TEST_BODY = "\n\ndef test_ok():\n    assert True\n"


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
    "    return dict(names=[])\n"
    "\n"
    "\n"
    "def guidance():\n"
    "    return dict(generator='Fake generator text.', test_author='Fake test text.')\n"
    "\n"
    "\n"
    "def provision(repo_root):\n"
    "    return dict(ok=True, reason='', versions=dict(fake='1.0'), lockfile_sha256=None)\n"
    "\n"
    "\n"
    "def asset_runner(asset_file):\n"
    "    path = Path(asset_file)\n"
    "\n"
    "    def run(entry, args):\n"
    "        for line in path.read_text().splitlines():\n"
    "            if line.startswith(entry + '='):\n"
    "                return int(line[len(entry) + 1:])\n"
    "        raise KeyError(entry)\n"
    "\n"
    "    return run\n"
    "\n"
    "\n"
    "def strength_sites(asset_file):\n"
    "    return [dict(description='1: a'), dict(description='2: b')]\n"
    "\n"
    "\n"
    "def apply_site(asset_file, site):\n"
    "    path = Path(asset_file)\n"
    "    lines = path.read_text().splitlines()\n"
    "    index = int(site['description'].split(':')[0]) - 1\n"
    "    key, value = lines[index].split('=')\n"
    "    lines[index] = key + '=' + str(int(value) + 1)\n"
    "    path.write_text('\\n'.join(lines) + '\\n')\n"
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
    "# Asset kind fake\n"
    "\n"
    "## Layout\n\nA text file of key=value lines.\n\n"
    "## Environment\n\nNo programs.\n\n"
    "## Surface\n\nNo names.\n\n"
    "## Running criteria\n\nasset_runner returns run(entry, args).\n\n"
    "## Strength check\n\nMutation: each line's number plus one.\n\n"
    "## Test author guidance\n\nFake test text.\n\n"
    "## Generator guidance\n\nFake generator text.\n"
)


ASSEMBLER_SOURCE = (
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    return dict(" + repr(BUNDLE) + ")\n"
)


PROBE_SOURCE = (
    "class _Report:\n"
    "    def __init__(self):\n"
    "        self.ok = True\n"
    "        self.findings = []\n"
    "        self.tests_run = 1\n"
    "        self.tests_reached = 1\n"
    "\n"
    "    def to_dict(self):\n"
    "        return dict(ok=self.ok, findings=list(self.findings), tests_run=self.tests_run, tests_reached=self.tests_reached)\n"
    "\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, *, timeout=60.0, interpreter=None):\n"
    "    return _Report()\n"
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
        repo_root / "specs" / "components" / SLUG / "component.md",
        frontmatter
        + "\n# Qux\n\n## Purpose\n\nReads a table.\n\n## Scope\n\n- In scope: reading.\n\n"
        "## Definitions\n\nNone.\n\n## Behavior\n\nSee `requirements/`.\n\n"
        "## Interfaces\n\nSee `interface/`.\n\n## Data\n\nSee `interface/data/`.\n\n"
        "## Acceptance criteria\n\nSee `acceptance/`.\n\n"
        "## Non-functional constraints\n\nSee `constraints.md`.\n\n"
        "## Open questions\n\n## Change log\n\n- Initial.\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "requirements" / "R-QUX-001.md",
        "# R-QUX-001\n\n**R-QUX-001** — The component MUST work.\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "acceptance" / "AC-QUX-001.md",
        "# AC-QUX-001\n\nCovers: R-QUX-001\nKind: generated-test\n\n"
        "```gherkin\nGiven a table\nWhen it is read\nThen it works\n```\n",
    )
    write(
        repo_root / "specs" / "components" / SLUG / "interface" / "library.md",
        "# Library\n\n```\nqux_read() -> int\n```\n",
    )
    write(repo_root / "specs" / "components" / SLUG / "constraints.md", "# Constraints\n\nNone.\n")
    write(
        repo_root / "specs" / "product" / "qux.md",
        "---\nid: P-QUX\ntitle: Qux capability\nstatus: draft\nowners: [team]\n---\n\n"
        "# Qux\n\n## Purpose\n\nQux.\n\n## Scope\n\n- Qux.\n",
    )
    write(repo_root / "specs" / "glossary.md", "# Glossary\n")

    write(repo_root / "gen" / SLUG / "qux.py", "")
    if with_assets:
        write(repo_root / "gen" / SLUG / "data" / "table.txt", "a=1\nb=2\n")
        write(repo_root / "specs" / "architecture" / "asset-kind-fake.md", FAKE_DEFINITION)
        write(repo_root / "gen" / "kind-fake" / "kind_fake.py", FAKE_ADAPTER_SOURCE)

    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", ASSEMBLER_SOURCE)
    write(repo_root / "gen" / "test-probe" / "test_probe.py", PROBE_SOURCE)

    write(
        repo_root / "verification" / SLUG / "generated-test" / "test_ac_qux_001.py",
        criterion_header() + PASSING_TEST_BODY,
    )
    return repo_root


def make_author(log_path):
    def author_stub(bundle):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        return {
            "component_id": COMPONENT_ID,
            "criterion_id": CRITERION_ID,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/qux/generated-test/test_ac_qux_001.py",
                "content": criterion_header() + PASSING_TEST_BODY,
            },
            "model_call_error": None,
            "repair_attempts": 0,
            "probe_findings": [],
        }

    return author_stub


def python_entry(repo_root):
    adapter_path = tool_gen_dir() / "kind-python" / "kind_python.py"
    kind_python = load_module(adapter_path, "kind_python")
    versions = kind_python.provision(Path(repo_root))["versions"]
    return {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": sha256_of_file(adapter_path),
        "versions": versions,
        "lockfile_sha256": None,
    }


def test_declared_fake_asset_is_reported_after_python(tmp_path):
    repo_root = build_fixture(tmp_path / "repo", with_assets=True)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_author(log_path)
    )

    p_entry = python_entry(repo_root)
    d = sha256_of_file(repo_root / "specs" / "architecture" / "asset-kind-fake.md")
    a = sha256_of_file(repo_root / "gen" / "kind-fake" / "kind_fake.py")
    expected = [
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
    assert field(report, "assets") == expected


def test_no_declared_assets_reports_only_python(tmp_path):
    repo_root = build_fixture(tmp_path / "repo", with_assets=False)
    log_path = tmp_path / "author.log"

    report = verifier_orchestrator.verify(
        COMPONENT_ID, repo_root, test_author=make_author(log_path)
    )

    assert field(report, "assets") == [python_entry(repo_root)]