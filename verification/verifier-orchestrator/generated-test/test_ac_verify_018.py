import json
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _get(value, name):
    if isinstance(value, dict):
        return value.get(name)
    try:
        return getattr(value, name)
    except AttributeError:
        pass
    try:
        return value[name]
    except Exception:
        return None


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FAKE_ASSEMBLER_TEMPLATE = '''import json
from pathlib import Path

_LOG = {log_path!r}


def _log(record):
    with open(_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\\n")


class _Bundle:
    def __init__(self, **kwargs):
        self._fields = dict(kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __getitem__(self, key):
        return self._fields[key]

    def get(self, key, default=None):
        return self._fields.get(key, default)

    def keys(self):
        return self._fields.keys()

    def __iter__(self):
        return iter(self._fields)

    def __len__(self):
        return len(self._fields)


def _slug(component_id):
    return component_id[len("comp-"):] if component_id.startswith("comp-") else component_id


def assemble(component_id, repo_root, mode="cold"):
    _log({{"fn": "assemble", "component_id": component_id, "mode": mode}})
    return _Bundle(
        component_id=component_id,
        spec_bundle_hash="sha256:" + "0" * 64,
        spec="spec",
        interface="# Library\\n\\n```\\ndouble(x: int) -> int\\n```",
        constraints="None.",
        dependency_interfaces={{}},
        dependency_context={{}},
        dependency_usage={{}},
        vars={{}},
        glossary="",
        hint_code=None,
    )


def assemble_criterion(component_id, criterion_id, repo_root):
    _log({{"fn": "assemble_criterion", "component_id": component_id, "criterion_id": criterion_id}})
    base = Path(repo_root) / "specs" / "components" / _slug(component_id)
    criterion_text = ""
    acc = base / "acceptance" / (str(criterion_id) + ".md")
    if acc.is_file():
        criterion_text = acc.read_text(encoding="utf-8")
    return _Bundle(
        component_id=component_id,
        criterion_id=criterion_id,
        covers="R-FOO-003",
        criterion_text=criterion_text,
        requirement_text="**R-FOO-003** — `double(x)` MUST return `2 * x`.",
        interface="# Library\\n\\n```\\ndouble(x: int) -> int\\n```",
        glossary="",
        dependency_interfaces={{}},
    )
'''


GENERATED_TEST_CONTENT = '''import importlib.util
import sys
from pathlib import Path


def _load():
    root = Path(__file__).resolve().parents[3]
    path = root / "gen" / "foo" / "foo.py"
    spec = importlib.util.spec_from_file_location("foo_under_test_ac_foo_003b", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["foo_under_test_ac_foo_003b"] = module
    spec.loader.exec_module(module)
    return module


def test_double():
    module = _load()
    assert module.double(2) == 4
'''


def _build_fixture(repo_root: Path, assembler_log: Path) -> None:
    _write(
        repo_root / "specs" / "glossary.md",
        "# Glossary\n\n- **Foo** — a test term.\n",
    )
    _write(
        repo_root / "specs" / "product" / "foo-capability.md",
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
        "- Doubling.\n"
        "\n"
        "## Capability scenarios\n"
        "\n"
        "### CS-FOO-001\n"
        "Covers: P-FOO\n"
        "Kind: generated-test\n"
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
        "# R-FOO-003\n\n**R-FOO-003** — `double(x)` MUST return `2 * x`.\n",
    )
    _write(
        comp / "acceptance" / "AC-FOO-003b.md",
        "# AC-FOO-003b\n"
        "\n"
        "Covers: R-FOO-003\n"
        "Kind: generated-test\n"
        "\n"
        "```gherkin\n"
        "Given a number x of 2\n"
        "When double is called with x\n"
        "Then it returns 4\n"
        "```\n",
    )
    _write(
        comp / "interface" / "library.md",
        "# Library\n\n```\ndouble(x: int) -> int\n```\n",
    )
    _write(comp / "constraints.md", "# Constraints\n\nNone.\n")

    # The unsealed component's real code.
    _write(
        repo_root / "gen" / "foo" / "foo.py",
        "def double(x):\n    return 2 * x\n",
    )

    # Fake spec-bundle-assembler, flat-module shape.
    _write(
        repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py",
        FAKE_ASSEMBLER_TEMPLATE.format(log_path=str(assembler_log)),
    )


def test_ac_verify_018_criterion_id_with_letter_suffix_passed_unchanged(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    logs = tmp_path / "logs"
    logs.mkdir()
    assembler_log = logs / "assembler.jsonl"
    author_log = logs / "test_author.jsonl"

    _build_fixture(repo_root, assembler_log)

    def test_author(bundle):
        criterion_id = _get(bundle, "criterion_id")
        component_id = _get(bundle, "component_id")
        with open(author_log, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"criterion_id": criterion_id,
                                 "component_id": component_id}) + "\n")
        return {
            "component_id": component_id,
            "criterion_id": criterion_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {
                "path": "verification/foo/generated-test/test_ac_foo_003b.py",
                "content": GENERATED_TEST_CONTENT,
            },
            "model_call_error": None,
        }

    report = verifier_orchestrator.verify("comp-foo", repo_root, test_author=test_author)

    criteria = field(report, "criteria")
    ids = [field(c, "id") for c in criteria]
    assert "AC-FOO-003b" in ids, f"criteria ids were {ids!r}"
    assert "AC-FOO-003B" not in ids
    assert "ac-foo-003b" not in ids
    matching = [c for c in criteria if field(c, "id") == "AC-FOO-003b"]
    assert len(matching) == 1

    # test_author was dispatched with a bundle for exactly "AC-FOO-003b".
    assert author_log.is_file(), "test_author was never called"
    author_records = [json.loads(line) for line in author_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert author_records, "test_author was never called"
    assert all(r["criterion_id"] == "AC-FOO-003b" for r in author_records), author_records

    # The bundle was assembled (via assemble_criterion) for exactly "AC-FOO-003b".
    assert assembler_log.is_file(), "spec-bundle-assembler fake was never invoked"
    asm_records = [json.loads(line) for line in assembler_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    crit_calls = [r for r in asm_records if r.get("fn") == "assemble_criterion"]
    assert crit_calls, f"assemble_criterion was never called; log: {asm_records!r}"
    assert [r["criterion_id"] for r in crit_calls] == ["AC-FOO-003b"] * len(crit_calls), crit_calls
    assert any(r["criterion_id"] == "AC-FOO-003b" for r in crit_calls)