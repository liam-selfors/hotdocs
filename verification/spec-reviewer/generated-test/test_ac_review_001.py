# hotdocs-criterion: sha256:2d71165e696e338e5df2c5000429f4a15ddbb71d980d7954301147ae78e60a3e
import importlib.util
import sys
from pathlib import Path

import pytest

import spec_reviewer


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def load_module(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def build_corpus(repo_root):
    specs = repo_root / "specs"
    write(
        specs / "glossary.md",
        "# Glossary\n"
        "\n"
        "- **Foo** \u2014 a test term.\n",
    )
    comp = specs / "components" / "foo"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "sealed: true\n"
        "source_path: legacy/foo/\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Foo doubles a number.\n",
    )
    write(
        comp / "requirements" / "R-FOO-001.md",
        "# R-FOO-001\n"
        "\n"
        "**R-FOO-001** \u2014 `foo(x)` MUST return `2 * x`.\n",
    )
    write(
        comp / "requirements" / "R-FOO-002.md",
        "# R-FOO-002\n"
        "\n"
        "**R-FOO-002** \u2014 `foo(x)` MUST return `0` for `x = 0`.\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n"
        "\n"
        "Covers: R-FOO-001\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 2\n"
        "When foo(x) is called\n"
        "Then it returns 4\n"
        "```\n",
    )
    write(
        comp / "acceptance" / "AC-FOO-002.md",
        "# AC-FOO-002\n"
        "\n"
        "Covers: R-FOO-002\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x = 0\n"
        "When foo(x) is called\n"
        "Then it returns 0\n"
        "```\n",
    )
    write(
        comp / "interface" / "library.md",
        "# Library\n"
        "\n"
        "```\n"
        "foo(x: int) -> int\n"
        "```\n",
    )
    write(
        comp / "constraints.md",
        "# Constraints\n"
        "\n"
        "None.\n",
    )


FAKE_LINTER = (
    "class Finding:\n"
    "    def __init__(self, rule_id, severity, file, line, message, rationale=None):\n"
    "        self.rule_id = rule_id\n"
    "        self.severity = severity\n"
    "        self.file = file\n"
    "        self.line = line\n"
    "        self.message = message\n"
    "        self.rationale = rationale\n"
    "\n"
    "\n"
    "class LintReport:\n"
    "    def __init__(self, findings):\n"
    "        self.findings = findings\n"
    "\n"
    "    @property\n"
    "    def hard_failures(self):\n"
    "        return sum(1 for f in self.findings if f.severity == 'fail')\n"
    "\n"
    "    @property\n"
    "    def warnings(self):\n"
    "        return sum(1 for f in self.findings if f.severity == 'warn')\n"
    "\n"
    "    @property\n"
    "    def skipped(self):\n"
    "        return sum(1 for f in self.findings if f.severity == 'skipped')\n"
    "\n"
    "    def to_json(self):\n"
    "        return {'findings': [], 'summary': {'hard_failures': 0, 'warnings': 0, 'skipped': 0}}\n"
    "\n"
    "\n"
    "def lint(paths, repo_root, strict=False, judge=None):\n"
    "    return LintReport([])\n"
    "\n"
    "\n"
    "def load_corpus(repo_root):\n"
    "    raise NotImplementedError('fake')\n"
)


FAKE_ASSEMBLER = (
    "from pathlib import Path\n"
    "\n"
    "\n"
    "class CriterionBundle:\n"
    "    _fields = ('component_id', 'criterion_id', 'covers', 'criterion_text',\n"
    "               'requirement_text', 'interface', 'glossary',\n"
    "               'dependency_interfaces', 'testing')\n"
    "\n"
    "    def __init__(self, component_id, criterion_id, covers, criterion_text,\n"
    "                 requirement_text, interface, glossary,\n"
    "                 dependency_interfaces=None, testing=''):\n"
    "        self.component_id = component_id\n"
    "        self.criterion_id = criterion_id\n"
    "        self.covers = covers\n"
    "        self.criterion_text = criterion_text\n"
    "        self.requirement_text = requirement_text\n"
    "        self.interface = interface\n"
    "        self.glossary = glossary\n"
    "        self.dependency_interfaces = dependency_interfaces or {}\n"
    "        self.testing = testing\n"
    "\n"
    "    def __getitem__(self, key):\n"
    "        if key not in self._fields:\n"
    "            raise KeyError(key)\n"
    "        return getattr(self, key)\n"
    "\n"
    "    def get(self, key, default=None):\n"
    "        return getattr(self, key) if key in self._fields else default\n"
    "\n"
    "    def keys(self):\n"
    "        return list(self._fields)\n"
    "\n"
    "    def __iter__(self):\n"
    "        return iter(self._fields)\n"
    "\n"
    "    def __len__(self):\n"
    "        return len(self._fields)\n"
    "\n"
    "\n"
    "def _read(path):\n"
    "    p = Path(path)\n"
    "    return p.read_text(encoding='utf-8').strip() if p.is_file() else ''\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    root = Path(repo_root)\n"
    "    slug = component_id[len('comp-'):] if component_id.startswith('comp-') else component_id\n"
    "    comp = root / 'specs' / 'components' / slug\n"
    "    crit = _read(comp / 'acceptance' / (criterion_id + '.md'))\n"
    "    covers = ''\n"
    "    for line in crit.splitlines():\n"
    "        if line.startswith('Covers:'):\n"
    "            covers = line[len('Covers:'):].strip()\n"
    "    req = _read(comp / 'requirements' / (covers + '.md')) if covers else ''\n"
    "    iface = _read(comp / 'interface' / 'library.md')\n"
    "    gloss = _read(root / 'specs' / 'glossary.md')\n"
    "    return CriterionBundle(component_id, criterion_id, covers, crit, req,\n"
    "                           iface, gloss, {}, '')\n"
    "\n"
    "\n"
    "def assemble(component_id, repo_root, mode='cold'):\n"
    "    raise NotImplementedError('fake')\n"
)


def write_fakes(repo_root):
    write(repo_root / "gen" / "spec-linter" / "spec_linter.py", FAKE_LINTER)
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        FAKE_ASSEMBLER,
    )


def find_real_linter():
    candidates = []
    here = Path(spec_reviewer.__file__).resolve()
    for p in here.parents:
        if p.name == "gen":
            candidates.append(p / "spec-linter")
        candidates.append(p / "gen" / "spec-linter")
    for p in [Path.cwd().resolve()] + list(Path.cwd().resolve().parents):
        candidates.append(p / "gen" / "spec-linter")
    for base in candidates:
        if (base / "spec_linter.py").is_file():
            return base / "spec_linter.py"
        if (base / "spec_linter" / "__init__.py").is_file():
            return base / "spec_linter" / "__init__.py"
    return None


def assert_lint_clean(repo_root):
    path = find_real_linter()
    if path is None:
        return
    spec_linter = load_module(path, "spec_linter")
    assert spec_linter.lint(None, repo_root).hard_failures == 0


@pytest.fixture
def repo_root(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    build_corpus(root)
    assert_lint_clean(root)
    write_fakes(root)
    return root


def test_component_and_criterion_targets_resolve_to_sorted_union(repo_root):
    report = spec_reviewer.check(["comp-foo", "AC-FOO-001"], repo_root)
    assert list(field(report, "criteria_checked")) == ["AC-FOO-001", "AC-FOO-002"]


def test_unknown_criterion_id_raises_value_error(repo_root):
    with pytest.raises(ValueError):
        spec_reviewer.check(["AC-FOO-009"], repo_root)


def test_unknown_component_id_raises_value_error(repo_root):
    with pytest.raises(ValueError):
        spec_reviewer.check(["comp-nothing"], repo_root)