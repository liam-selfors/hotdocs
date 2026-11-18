# hotdocs-criterion: sha256:341656d6636d8da9ebf6b6dac068ffaa61a8f3e6ffb9ada234e76de28f00fabb
"""AC-VERIFY-014 (covers R-VERIFY-013).

Two separate repo_root directories, both declaring component ``comp-foo``
(slug ``foo``) but with different code, verified one after the other in
the same process. Each call's interface-drift result and compiled-criterion
results must reflect that call's own repo_root's code, never a module
cached from the other repo_root's earlier call.
"""

from pathlib import Path

import pytest

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


COMPONENT_MD = (
    "---\n"
    "id: comp-foo\n"
    "title: Foo\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "realizes: [P-FOO]\n"
    "depends_on: []\n"
    "---\n"
    "\n"
    "# Foo\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Foo doubles a number.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: doubling.\n"
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
    "id: P-FOO\n"
    "title: Foo capability\n"
    "status: draft\n"
    "owners: [team-a]\n"
    "---\n"
    "\n"
    "# Foo capability\n"
    "\n"
    "## Purpose\n"
    "\n"
    "Doubling numbers.\n"
    "\n"
    "## Scope\n"
    "\n"
    "- In scope: doubling.\n"
)

GLOSSARY_MD = "# Glossary\n\n- **Foo** — a test term.\n"

REQUIREMENT_MD = "# R-FOO-001\n\n**R-FOO-001** — `double(x)` MUST return `2 * x`.\n"

ACCEPTANCE_MD = (
    "# AC-FOO-001\n"
    "\n"
    "Covers: R-FOO-001\n"
    "Kind: compiled\n"
    "\n"
    "```gherkin\n"
    "Given a n is 2\n"
    "When double is invoked with [2]\n"
    "Then result equals 4\n"
    "```\n"
)

LIBRARY_MD = "# Library\n\n```\ndouble(x: int) -> int\n```\n"

CONSTRAINTS_MD = "# Constraints\n\nNone.\n"

# Component code: variant "a" matches the interface (no drift); variant "b"
# lacks the declared `double` (drift).
COMPONENT_CODE = {
    "a": "def double(x):\n    return 2 * x\n",
    "b": "def halve(x):\n    return x // 2\n",
}

# The compiled test each repo's own criterion-compiler emits: passes in "a",
# fails in "b".
COMPILED_SOURCE = {
    "a": "def test_compiled():\n    assert True\n",
    "b": "def test_compiled():\n    assert False, 'variant b compiler'\n",
}

COMPILER_BODY = (
    "import dataclasses\n"
    "from pathlib import Path\n"
    "\n"
    "GATE_VERSION = 'criterion-compiler@1.0.0'\n"
    "\n"
    "\n"
    "def _log(what):\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(VARIANT + ' ' + what + '\\n')\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class ParsedCriterion:\n"
    "    criterion_id: str = ''\n"
    "    covers: str = ''\n"
    "    kind: str = ''\n"
    "    gherkin: str = ''\n"
    "    file: str = ''\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class InterfaceSurface:\n"
    "    functions: dict = dataclasses.field(default_factory=dict)\n"
    "    types: dict = dataclasses.field(default_factory=dict)\n"
    "    module_name: str = ''\n"
    "\n"
    "\n"
    "@dataclasses.dataclass\n"
    "class CompileReport:\n"
    "    outputs: list = dataclasses.field(default_factory=list)\n"
    "    gate_version: str = GATE_VERSION\n"
    "    summary: dict = dataclasses.field(default_factory=dict)\n"
    "\n"
    "\n"
    "def _parse(text):\n"
    "    covers = ''\n"
    "    kind = 'compiled'\n"
    "    for line in text.splitlines():\n"
    "        s = line.strip()\n"
    "        if s.startswith('Covers:') and not covers:\n"
    "            covers = s[len('Covers:'):].strip()\n"
    "        elif s.startswith('Kind:'):\n"
    "            kind = s[len('Kind:'):].strip()\n"
    "    return covers, kind\n"
    "\n"
    "\n"
    "def compile(component_id, repo_root, target='pytest', out_dir=None):\n"
    "    _log('compile')\n"
    "    slug = component_id[5:] if component_id.startswith('comp-') else component_id\n"
    "    root = Path(repo_root)\n"
    "    out = Path(out_dir) if out_dir is not None else root / 'verification' / slug / 'compiled'\n"
    "    out.mkdir(parents=True, exist_ok=True)\n"
    "    outputs = []\n"
    "    compiled = 0\n"
    "    skipped = 0\n"
    "    acc = root / 'specs' / 'components' / slug / 'acceptance'\n"
    "    for path in sorted(acc.glob('AC-*.md')):\n"
    "        cid = path.stem\n"
    "        covers, kind = _parse(path.read_text(encoding='utf-8'))\n"
    "        if kind != 'compiled':\n"
    "            skipped += 1\n"
    "            continue\n"
    "        target_file = out / ('test_' + cid.lower().replace('-', '_') + '.py')\n"
    "        target_file.write_text(SOURCE, encoding='utf-8')\n"
    "        try:\n"
    "            rel = str(target_file.resolve().relative_to(root.resolve()))\n"
    "        except ValueError:\n"
    "            rel = str(target_file.resolve())\n"
    "        outputs.append({'criterion_id': cid, 'covers': covers,\n"
    "                        'status': 'compiled', 'file': rel})\n"
    "        compiled += 1\n"
    "    return CompileReport(outputs=outputs, gate_version=GATE_VERSION,\n"
    "                         summary={'compiled': compiled, 'errors': 0,\n"
    "                                  'skipped_non_compiled_kind': skipped})\n"
    "\n"
    "\n"
    "def compile_criterion(criterion, surface=None):\n"
    "    _log('compile_criterion')\n"
    "    return {'status': 'compiled', 'source': SOURCE}\n"
)

ASSEMBLER_BODY = (
    "from pathlib import Path\n"
    "\n"
    "\n"
    "def assemble_criterion(component_id, criterion_id, repo_root):\n"
    "    with open(LOG, 'a', encoding='utf-8') as fh:\n"
    "        fh.write(VARIANT + ' assemble_criterion\\n')\n"
    "    return {\n"
    "        'component_id': component_id,\n"
    "        'criterion_id': criterion_id,\n"
    "        'covers': 'R-FOO-001',\n"
    "        'criterion_text': 'criterion text',\n"
    "        'requirement_text': 'requirement text',\n"
    "        'interface': 'interface text',\n"
    "        'glossary': 'glossary text',\n"
    "        'dependency_interfaces': {},\n"
    "    }\n"
)


def build_fixture(repo_root, variant, compiler_log, assembler_log):
    repo_root = Path(repo_root)
    comp = repo_root / "specs" / "components" / "foo"
    write(repo_root / "specs" / "glossary.md", GLOSSARY_MD)
    write(repo_root / "specs" / "product" / "foo.md", PRODUCT_MD)
    write(comp / "component.md", COMPONENT_MD)
    write(comp / "requirements" / "R-FOO-001.md", REQUIREMENT_MD)
    write(comp / "acceptance" / "AC-FOO-001.md", ACCEPTANCE_MD)
    write(comp / "interface" / "library.md", LIBRARY_MD)
    write(comp / "constraints.md", CONSTRAINTS_MD)
    write(repo_root / "gen" / "foo" / "foo.py", COMPONENT_CODE[variant])

    compiler_src = (
        "LOG = " + repr(str(compiler_log)) + "\n"
        + "VARIANT = " + repr(variant) + "\n"
        + "SOURCE = " + repr(COMPILED_SOURCE[variant]) + "\n"
        + COMPILER_BODY
    )
    write(
        repo_root / "pipeline" / "criterion-compiler" / "criterion_compiler.py",
        compiler_src,
    )

    assembler_src = (
        "LOG = " + repr(str(assembler_log)) + "\n"
        + "VARIANT = " + repr(variant) + "\n"
        + ASSEMBLER_BODY
    )
    write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        assembler_src,
    )
    return repo_root


def read_lines(path):
    path = Path(path)
    if not path.is_file():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line]


def criterion_result(report, criterion_id):
    criteria = field(report, "criteria")
    matches = [c for c in criteria if field(c, "id") == criterion_id]
    assert len(matches) == 1, "expected exactly one entry for " + criterion_id
    return field(matches[0], "result")


EXPECTED = {
    "a": {"result": "pass", "drift": False},
    "b": {"result": "fail", "drift": True},
}


@pytest.mark.parametrize("order", [("a", "b"), ("b", "a")])
def test_each_repo_root_uses_its_own_modules(tmp_path, order):
    logs = tmp_path / "logs"
    logs.mkdir()
    repos = {}
    compiler_logs = {}
    for variant in ("a", "b"):
        compiler_logs[variant] = logs / ("compiler_" + variant + ".log")
        repos[variant] = build_fixture(
            tmp_path / ("repo_" + variant),
            variant,
            compiler_logs[variant],
            logs / ("assembler_" + variant + ".log"),
        )

    for variant in order:
        other = "b" if variant == "a" else "a"
        before_own = len(read_lines(compiler_logs[variant]))
        before_other = len(read_lines(compiler_logs[other]))

        report = verifier_orchestrator.verify("comp-foo", repos[variant])

        assert field(report, "component_id") == "comp-foo"
        assert criterion_result(report, "AC-FOO-001") == EXPECTED[variant]["result"], (
            "compiled criterion result for repo " + variant
            + " does not reflect its own criterion-compiler"
        )
        assert field(report, "interface_drift") is EXPECTED[variant]["drift"], (
            "interface drift for repo " + variant
            + " does not reflect its own gen/foo/ code"
        )

        own_lines = read_lines(compiler_logs[variant])
        assert len(own_lines) > before_own, (
            "repo " + variant + "'s own criterion-compiler was never loaded"
        )
        assert all(line.startswith(variant + " ") for line in own_lines)
        assert len(read_lines(compiler_logs[other])) == before_other, (
            "verifying repo " + variant
            + " ran the other repo_root's criterion-compiler"
        )