# hotdocs-criterion: sha256:32c5dbdcf728535996fa427df66b88317c9b1d8695b5b18c9a55188c2a7f9789
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


def as_plain(entry):
    if isinstance(entry, dict):
        return dict(entry)
    if hasattr(entry, "to_dict"):
        return entry.to_dict()
    return dict(vars(entry))


def sha_of_file(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


BUNDLE = {
    "component_id": "comp-qux",
    "criterion_id": "AC-QUX-001",
    "covers": "R-QUX-001",
    "criterion_text": "Given a qux When checked Then it holds",
    "requirement_text": "R-QUX-001 qux MUST hold.",
    "interface": "# Library\n\nqux_value() -> int",
    "glossary": "# Glossary",
    "dependency_interfaces": {},
    "testing": "",
}


def header_line():
    keys = ("criterion_text", "requirement_text", "interface", "glossary", "testing")
    payload = json.dumps(
        {k: BUNDLE[k] for k in keys},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return "# hotdocs-criterion: sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


FAKE_ADAPTER = (
    "from pathlib import Path\n"
    "\n"
    "KIND = 'fake'\n"
    "\n"
    "def layout_errors(*args, **kwargs):\n"
    "    return []\n"
    "\n"
    "def surface(*args, **kwargs):\n"
    "    return {'names': []}\n"
    "\n"
    "def guidance():\n"
    "    return {'generator': 'Fake generator text.', 'test_author': 'Fake test text.'}\n"
    "\n"
    "def provision(repo_root):\n"
    "    return {'ok': True, 'reason': '', 'versions': {'fake': '1.0'}, 'lockfile_sha256': None}\n"
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
    "def strength_sites(asset_file):\n"
    "    return [{'description': '1: a'}, {'description': '2: b'}]\n"
    "\n"
    "def apply_site(asset_file, site):\n"
    "    path = Path(asset_file)\n"
    "    lines = path.read_text().splitlines()\n"
    "    index = int(site['description'].split(':')[0]) - 1\n"
    "    key, _, value = lines[index].partition('=')\n"
    "    lines[index] = key + '=' + str(int(value) + 1)\n"
    "    path.write_text('\\n'.join(lines) + '\\n')\n"
)

PROBE_STAND_IN = (
    "class _Report:\n"
    "    def __init__(self):\n"
    "        self.ok = True\n"
    "        self.findings = []\n"
    "    def to_dict(self):\n"
    "        return {'ok': True, 'findings': []}\n"
    "\n"
    "def probe(test_source, criterion_bundle, module_name, **kwargs):\n"
    "    return _Report()\n"
)


def assembler_stand_in():
    return (
        "BUNDLE = " + repr(BUNDLE) + "\n"
        "\n"
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    result = dict(BUNDLE)\n"
        "    result['component_id'] = component_id\n"
        "    result['criterion_id'] = criterion_id\n"
        "    return result\n"
    )


CACHED_TEST_BODY = (
    "\n"
    "\n"
    "def test_qux_holds():\n"
    "    assert 1 + 1 == 2\n"
)


def build_fixture(root, with_assets):
    root = Path(root)
    frontmatter = (
        "---\n"
        "id: comp-qux\n"
        "title: Qux\n"
        "status: draft\n"
        "owners: [qux-team]\n"
        "depends_on: []\n"
        "realizes: [P-QUX]\n"
    )
    if with_assets:
        frontmatter += "assets: [fake:data/table.txt]\n"
    frontmatter += "---\n\n# Qux\n\n## Purpose\n\nA fixture component.\n"
    write(root / "specs/components/qux/component.md", frontmatter)
    write(
        root / "specs/product/qux.md",
        "---\n"
        "id: P-QUX\n"
        "title: Qux capability\n"
        "status: draft\n"
        "owners: [qux-team]\n"
        "---\n\n# P-QUX\n\nThe qux capability.\n",
    )
    write(
        root / "specs/components/qux/requirements/R-QUX-001.md",
        "# R-QUX-001\n\n**R-QUX-001** — qux MUST hold.\n",
    )
    write(
        root / "specs/components/qux/interface/library.md",
        "# Library\n\n```\nqux_value() -> int\n```\n",
    )
    write(
        root / "specs/components/qux/acceptance/AC-QUX-001.md",
        "# AC-QUX-001\n\n"
        "Covers: R-QUX-001\n"
        "Kind: generated-test\n\n"
        "```gherkin\n"
        "Given a qux\n"
        "When checked\n"
        "Then it holds\n"
        "```\n",
    )
    write(root / "specs/glossary.md", "# Glossary\n")
    write(root / "gen/qux/qux.py", "")
    write(root / "gen/spec-bundle-assembler/spec_bundle_assembler.py", assembler_stand_in())
    write(root / "gen/test-probe/test_probe.py", PROBE_STAND_IN)
    write(
        root / "verification/qux/generated-test/test_ac_qux_001.py",
        header_line() + CACHED_TEST_BODY,
    )
    if with_assets:
        write(root / "gen/qux/data/table.txt", "a=1\nb=2\n")
        write(root / "specs/architecture/asset-kind-fake.md", "# Fake asset kind\n\nAny text.\n")
        write(root / "gen/kind-fake/kind_fake.py", FAKE_ADAPTER)


def make_author(log_path):
    def author_stand_in(bundle):
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
                "content": header_line() + CACHED_TEST_BODY,
            },
        }

    return author_stand_in


def python_entry(repo_root):
    adapter_path = Path(verifier_orchestrator.__file__).parents[1] / "kind-python" / "kind_python.py"
    adapter = load_module(adapter_path, "kind_python")
    versions = adapter.provision(repo_root)["versions"]
    return {
        "kind": "python",
        "path": ".",
        "definition_sha256": None,
        "adapter_sha256": sha_of_file(adapter_path),
        "versions": versions,
        "lockfile_sha256": None,
    }


def run_verify(repo_root):
    log = Path(repo_root) / "author.log"
    report = verifier_orchestrator.verify(
        "comp-qux", Path(repo_root), test_author=make_author(log)
    )
    return report


def test_assets_with_declared_fake_kind(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, with_assets=True)

    report = run_verify(repo_root)

    p = python_entry(repo_root)
    d = sha_of_file(repo_root / "specs/architecture/asset-kind-fake.md")
    a = sha_of_file(repo_root / "gen/kind-fake/kind_fake.py")
    expected = [
        p,
        {
            "kind": "fake",
            "path": "data/table.txt",
            "definition_sha256": d,
            "adapter_sha256": a,
            "versions": {"fake": "1.0"},
            "lockfile_sha256": None,
        },
    ]
    assets = [as_plain(e) for e in field(report, "assets")]
    assert assets == expected


def test_assets_with_no_declared_assets(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root, with_assets=False)

    report = run_verify(repo_root)

    p = python_entry(repo_root)
    assets = [as_plain(e) for e in field(report, "assets")]
    assert assets == [p]