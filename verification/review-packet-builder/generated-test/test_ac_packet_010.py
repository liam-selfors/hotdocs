# hotdocs-criterion: sha256:140b82caa31037bf27f6cf35af6b97f2860b96fcc72719d441633f33fed0369a
import dataclasses
import subprocess
from pathlib import Path

import review_packet_builder


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", *args],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _gen_code(tag, count):
    lines = ["# generated module " + tag + "\n", "import os\n", "\n"]
    for i in range(count):
        lines.append("def " + tag.lower() + "_func_" + str(i) + "(x):\n")
        lines.append("    value = " + repr(tag + "_value_" + str(i)) + "\n")
        lines.append("    return x + len(value) * " + str(i) + "\n")
        lines.append("\n")
    return "".join(lines)


def _all_strings(value, seen=None):
    if seen is None:
        seen = set()
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, bytes):
        yield value.decode("utf-8", "replace")
        return
    if value is None or isinstance(value, (bool, int, float)):
        return
    if id(value) in seen:
        return
    seen.add(id(value))
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _all_strings(k, seen)
            yield from _all_strings(v, seen)
        return
    if isinstance(value, (list, tuple, set, frozenset)):
        for item in value:
            yield from _all_strings(item, seen)
        return
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        for f in dataclasses.fields(value):
            yield from _all_strings(getattr(value, f.name), seen)
        return
    if hasattr(value, "__dict__"):
        for v in vars(value).values():
            yield from _all_strings(v, seen)
        return
    yield str(value)


def _component_md():
    return (
        "---\n"
        "id: comp-foo\n"
        "title: Foo\n"
        "status: draft\n"
        "owners: [alice]\n"
        "depends_on: []\n"
        "---\n"
        "\n"
        "# Foo\n"
        "\n"
        "A fixture component.\n"
    )


def _requirement(text):
    return "# R-FOO-001\n\n**R-FOO-001** — " + text + "\n"


def _stand_in(log_path):
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "mutation_error": None,
        "overall": "pass",
    }
    report = {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": verification_report,
                "license_scan": {"blocked": False, "findings": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }
    return (
        "LOG_PATH = " + repr(str(log_path)) + "\n"
        "REPORT = " + repr(report) + "\n"
        "\n"
        "\n"
        "def _log(line):\n"
        "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
        "        fh.write(line + '\\n')\n"
        "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    _log('check_readiness')\n"
        "    import copy\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    _log('last_requirement_failures')\n"
        "    return []\n"
    )


def test_packet_contains_no_generated_code_diff(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    log_path = tmp_path / "stand_in_calls.log"

    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(comp_dir / "component.md", _component_md())
    _write(comp_dir / "requirements" / "R-FOO-001.md", _requirement("Foo MUST return a value."))
    _write(
        comp_dir / "acceptance" / "AC-FOO-001.md",
        "# AC-FOO-001\n\nCovers: R-FOO-001\nKind: compiled\n\nfoo returns a value.\n",
    )
    _write(comp_dir / "interface" / "library.md", "# Library\n\n```\nfoo(x) -> int\n```\n")
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")

    gen_file = repo_root / "gen" / "foo" / "foo.py"
    _write(gen_file, _gen_code("GENOLD_7f3e", 40))
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", _stand_in(log_path))

    _git(repo_root, "init")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "base")

    # Committed change: spec edit plus a substantial rewrite of generated code.
    _write(comp_dir / "requirements" / "R-FOO-001.md", _requirement("Foo MUST return a doubled value."))
    _write(gen_file, _gen_code("GENNEW_c91a", 60))
    _write(repo_root / "gen" / "foo" / "helpers.py", _gen_code("GENADD_e44b", 30))
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "change foo")

    # Further uncommitted change, so a working-tree diff also sees generated code churn.
    _write(comp_dir / "requirements" / "R-FOO-001.md", _requirement("Foo MUST return a tripled value."))
    _write(gen_file, _gen_code("GENWT_5b2d", 50))

    packet = review_packet_builder.build_review_packet(["comp-foo", "R-FOO-001"], repo_root)

    assert log_path.is_file() and "check_readiness" in log_path.read_text(encoding="utf-8")

    # Sanity: the packet is a real packet with its documented fields.
    field(packet, "spec_diff")
    field(packet, "regenerated_components")

    strings = list(_all_strings(packet))
    markers = [
        "GENOLD_7f3e",
        "genold_7f3e_func",
        "GENNEW_c91a",
        "gennew_c91a_func",
        "GENADD_e44b",
        "genadd_e44b_func",
        "GENWT_5b2d",
        "genwt_5b2d_func",
        "# generated module",
        "return x + len(value)",
    ]
    diff_headers = [
        "a/gen/foo/",
        "b/gen/foo/",
        "--- a/gen/",
        "+++ b/gen/",
        "diff --git a/gen/",
    ]
    for s in strings:
        for marker in markers:
            assert marker not in s, "generated code content found in packet: " + repr(marker)
        for header in diff_headers:
            assert header not in s, "generated code diff header found in packet: " + repr(header)