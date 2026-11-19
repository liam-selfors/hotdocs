# hotdocs-criterion: sha256:04c4f9672d8633ccb1a4bccda5c0eb210d83a947107d9652ceb5fb49b592a0aa
import json
import re
from pathlib import Path

import verifier_orchestrator


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


ASSEMBLER_SOURCE = r'''import re
from pathlib import Path


def assemble_criterion(component_id, criterion_id, repo_root):
    slug = component_id[len("comp-"):] if component_id.startswith("comp-") else component_id
    base = Path(repo_root) / "specs" / "components" / slug
    text = (base / "acceptance" / (criterion_id + ".md")).read_text(encoding="utf-8")
    m = re.search(r"Covers:\s*(\S+)", text)
    covers = m.group(1) if m else ""
    req = base / "requirements" / (covers + ".md")
    requirement_text = req.read_text(encoding="utf-8") if req.is_file() else ""
    lib = base / "interface" / "library.md"
    interface = lib.read_text(encoding="utf-8") if lib.is_file() else ""
    return {
        "component_id": component_id,
        "criterion_id": criterion_id,
        "covers": covers,
        "criterion_text": text,
        "requirement_text": requirement_text,
        "interface": interface,
        "glossary": "",
        "dependency_interfaces": {},
    }
'''


def acceptance(ac_id, covers, kind, marker):
    return (
        "# " + ac_id + "\n"
        "\n"
        "Covers: " + covers + "\n"
        "Kind: " + kind + "\n"
        "\n"
        "```gherkin\n"
        "Given a " + marker + " is 2\n"
        "When double is invoked with [2]\n"
        "Then result equals 4\n"
        "```\n"
    )


def build_fixture(repo_root):
    write(repo_root / "specs" / "glossary.md", "# Glossary\n\n- **Foo** — a test term.\n")
    write(
        repo_root / "specs" / "product" / "foo-capability.md",
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
        "Doubling numbers.\n",
    )
    comp = repo_root / "specs" / "components" / "foo"
    write(
        comp / "component.md",
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
        "Foo doubles a number.\n",
    )
    for rid, text in (
        ("R-FOO-001", "`double(x)` MUST return `2 * x`."),
        ("R-FOO-002", "`double(x)` MUST accept negative numbers."),
        ("R-FOO-003", "The doubling MUST be clearly documented."),
    ):
        write(comp / "requirements" / (rid + ".md"), "# " + rid + "\n\n**" + rid + "** — " + text + "\n")
    write(comp / "interface" / "library.md", "# Library\n\n```\ndouble(x: int) -> int\n```\n")
    write(comp / "constraints.md", "# Constraints\n\nNone.\n")
    write(comp / "acceptance" / "AC-FOO-001.md", acceptance("AC-FOO-001", "R-FOO-001", "generated-test", "zebrafish"))
    write(comp / "acceptance" / "AC-FOO-002.md", acceptance("AC-FOO-002", "R-FOO-001", "generated-test", "kumquat"))
    write(comp / "acceptance" / "AC-FOO-003.md", acceptance("AC-FOO-003", "R-FOO-002", "generated-test", "platypus"))
    write(comp / "acceptance" / "AC-FOO-004.md", acceptance("AC-FOO-004", "R-FOO-003", "llm-judge", "quokka"))

    write(repo_root / "gen" / "foo" / "foo.py", "")
    write(repo_root / "gen" / "spec-bundle-assembler" / "spec_bundle_assembler.py", ASSEMBLER_SOURCE)


PASSING_TEST = "def test_ok():\n    assert True\n"
FAILING_TEST = "def test_bad():\n    assert 3 == 5\n"


def make_test_author(log_path):
    def test_author(bundle):
        criterion_id = field(bundle, "criterion_id")
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(str(criterion_id) + "\n")
        content = FAILING_TEST if criterion_id == "AC-FOO-003" else PASSING_TEST
        name = "test_" + str(criterion_id).lower().replace("-", "_") + ".py"
        return {
            "component_id": "comp-foo",
            "criterion_id": criterion_id,
            "model": "fake-model",
            "seed": 0,
            "prompt_version": "v1",
            "cache_hit": False,
            "file": {"path": "verification/foo/generated-test/" + name, "content": content},
            "model_call_error": None,
        }

    return test_author


def test_requirement_results_projects_criteria_and_is_boolean_only(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    build_fixture(repo_root)
    log_path = tmp_path / "author_calls.log"

    report = verifier_orchestrator.verify(
        "comp-foo", repo_root, test_author=make_test_author(log_path)
    )

    rr = field(report, "requirement_results")
    assert isinstance(rr, dict)
    assert rr == {"R-FOO-001": "pass", "R-FOO-002": "fail", "R-FOO-003": "fail"}

    for key, value in rr.items():
        assert isinstance(key, str) and re.fullmatch(r"R-[A-Z0-9]+-\d+", key)
        assert value in ("pass", "fail")

    dumped = json.dumps(rr)
    forbidden = [
        "Given", "When", "Then", "gherkin", "rationale", "expected", "actual",
        "failure_detail", "message", "AC-FOO", "zebrafish", "kumquat",
        "platypus", "quokka", "double", "result equals", "assert",
    ]
    for word in forbidden:
        assert word not in dumped, word

    if hasattr(report, "to_dict"):
        as_dict = report.to_dict()
        assert as_dict["requirement_results"] == {
            "R-FOO-001": "pass", "R-FOO-002": "fail", "R-FOO-003": "fail"
        }