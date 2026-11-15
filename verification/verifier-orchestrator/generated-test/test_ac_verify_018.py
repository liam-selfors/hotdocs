import verifier_orchestrator

import json
from pathlib import Path


CRITERION_ID = "AC-FOO-003b"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def bundle_field(bundle, name):
    if isinstance(bundle, dict):
        return bundle[name]
    if hasattr(bundle, name):
        return getattr(bundle, name)
    return bundle[name]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FAKE_ASSEMBLER_TEMPLATE = '''import json
import hashlib

_LOG_PATH = {log_path!r}


def _log(record):
    with open(_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


class _MappingRecord:
    _fields = ()

    def __getitem__(self, key):
        if key not in self._fields:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key, default=None):
        if key in self._fields:
            return getattr(self, key)
        return default

    def keys(self):
        return list(self._fields)

    def items(self):
        return [(k, getattr(self, k)) for k in self._fields]

    def values(self):
        return [getattr(self, k) for k in self._fields]

    def __iter__(self):
        return iter(self._fields)

    def __contains__(self, key):
        return key in self._fields

    def __len__(self):
        return len(self._fields)

    def to_dict(self):
        return {{k: getattr(self, k) for k in self._fields}}


class SpecBundle(_MappingRecord):
    _fields = (
        "component_id", "spec_bundle_hash", "spec", "interface", "constraints",
        "dependency_interfaces", "dependency_context", "dependency_usage",
        "vars", "glossary", "hint_code",
    )

    def __init__(self, **kw):
        for k in self._fields:
            setattr(self, k, kw.get(k))


class CriterionBundle(_MappingRecord):
    _fields = (
        "component_id", "criterion_id", "covers", "criterion_text",
        "requirement_text", "interface", "glossary", "dependency_interfaces",
    )

    def __init__(self, **kw):
        for k in self._fields:
            setattr(self, k, kw.get(k))


_INTERFACE = "# Library\\n\\n```\\ndouble(x: int) -> int\\n```"


def assemble(component_id, repo_root, mode="cold"):
    _log({{"fn": "assemble", "component_id": component_id, "mode": mode}})
    digest = hashlib.sha256(("fake:" + str(component_id)).encode("utf-8")).hexdigest()
    return SpecBundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + digest,
        spec="# Foo\\n\\n## Purpose\\n\\nFoo doubles a number.",
        interface=_INTERFACE,
        constraints="# Constraints\\n\\nNone.",
        dependency_interfaces={{}},
        dependency_context={{}},
        dependency_usage={{}},
        vars={{}},
        glossary="# Glossary\\n\\n- **Foo** \\u2014 a test term.",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log({{"fn": "assemble_criterion", "component_id": component_id,
           "criterion_id": criterion_id}})
    return CriterionBundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-003",
        criterion_text="Given x is 2\\nWhen double is invoked with 2\\nThen result equals 4",
        requirement_text="**R-FOO-003** \\u2014 `double(x)` MUST return `2 * x`.",
        interface=_INTERFACE,
        glossary="# Glossary\\n\\n- **Foo** \\u2014 a test term.",
        dependency_interfaces={{}},
    )
'''


def _build_fixture(repo_root: Path, assembler_log: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** \u2014 a test term.\n",
    )
    _write(
        repo_root / "specs" / "product" / "P-FOO.md",
        "---\n"
        "id: P-FOO\n"
        "title: Foo Capability\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "---\n"
        "\n"
        "# Foo Capability\n"
        "\n"
        "## Purpose\n"
        "\n"
        "Doubling numbers.\n"
        "\n"
        "## Scope\n"
        "\n"
        "- In scope: doubling.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-FOO-001\n"
        "\n"
        "Covers: P-FOO\n"
        "Kind: compiled\n"
        "\n"
        "```gherkin\n"
        "Given x is 2\n"
        "When double is invoked with 2\n"
        "Then result equals 4\n"
        "```\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    _write(
        comp / "component.md",
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "realizes: [P-FOO]\n"
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
        "- Initial.\n",
    )
    _write(
        comp / "requirements" / "R-FOO-003.md",
        "# R-FOO-003\n\n**R-FOO-003** \u2014 `double(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-003b.md",
        "# AC-FOO-003b\n"
        "\n"
        "Covers: R-FOO-003\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given x is 2\n"
        "When double is invoked with 2\n"
        "Then result equals 4\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble(x: int) -> int\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    _write(
        repo_root / "gen" / "foo" / "foo.py",
        "def double(x):\n    return 2 * x\n",
    )

    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        FAKE_ASSEMBLER_TEMPLATE.format(log_path=str(assembler_log)),
    )


def _read_log(path: Path):
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_suffixed_criterion_id_taken_exactly_from_heading(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    assembler_log = logs / "assembler.jsonl"
    author_log = logs / "test_author.jsonl"

    _build_fixture(repo_root, assembler_log)

    def test_author(bundle):
        crit_id = bundle_field(bundle, "criterion_id")
        comp_id = bundle_field(bundle, "component_id")
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"criterion_id": crit_id, "component_id": comp_id}) + "\n")
        content = (
            "import foo\n"
            "\n"
            "\n"
            "def test_double():\n"
            "    assert foo.double(2) == 4\n"
            "    assert foo.double(3) == 6\n"
        )
        return {
            "component_id": comp_id,
            "criterion_id": crit_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/foo/generated-test/test_ac_foo_003b.py",
                "content": content,
            },
            "model_call_error": None,
        }

    report = verifier_orchestrator.verify("comp-foo", repo_root, test_author=test_author)

    criteria = field(report, "criteria")
    ids = [field(c, "id") for c in criteria]

    # The criteria entry's id is exactly the heading's id, suffix and case preserved.
    assert ids == [CRITERION_ID], ids
    assert "AC-FOO-003B" not in ids
    assert "ac-foo-003b" not in ids

    # The bundle handed to test_author was assembled for exactly "AC-FOO-003b".
    assemble_calls = [r for r in _read_log(assembler_log) if r["fn"] == "assemble_criterion"]
    assert assemble_calls, "assemble_criterion was never called"
    assert all(r["criterion_id"] == CRITERION_ID for r in assemble_calls), assemble_calls
    assert all(r["component_id"] == "comp-foo" for r in assemble_calls), assemble_calls

    author_calls = _read_log(author_log)
    assert author_calls, "test_author was never called"
    assert all(r["criterion_id"] == CRITERION_ID for r in author_calls), author_calls