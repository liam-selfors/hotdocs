import review_packet_builder

import dataclasses
import json
import os
import subprocess
from pathlib import Path


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


MARKERS = [
    "GENCODE_MARKER_OLD_ZQ7X",
    "GENCODE_MARKER_NEW_K4VW",
    "GENCODE_MARKER_WT_P9RJ",
    "zq7x_old_helper",
    "k4vw_new_helper",
    "p9rj_worktree_helper",
]


def _git(repo_root, *args):
    subprocess.run(
        [
            "git",
            "-c", "user.name=Test",
            "-c", "user.email=test@example.com",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo_root),
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _gen_code(tag, helper, n):
    lines = [
        '"""Generated module for comp-foo (%s)."""' % tag,
        "",
        "SENTINEL = %r" % tag,
        "",
    ]
    for i in range(n):
        lines.append("def %s_%d(x):" % (helper, i))
        lines.append("    # %s line %d" % (tag, i))
        lines.append("    return x * %d + len(%r)" % (i + 1, tag))
        lines.append("")
    return "\n".join(lines) + "\n"


COMPONENT_MD = """---
id: comp-foo
title: Foo
status: draft
owners: [alice]
depends_on: []
---

# Foo

A synthetic component used to exercise the review packet builder.
"""


def _requirement(text):
    return "# R-FOO-001\n\n**R-FOO-001** — %s\n" % text


ACCEPTANCE = """# AC-FOO-001

Covers: R-FOO-001
Kind: generated-test

```gherkin
Given a foo
When it runs
Then it returns a value
```
"""


def _verify_report():
    verification_report = {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "generated-test", "result": "pass"}
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": 1.0,
        "overall": "pass",
    }
    return {
        "scope": "blast-radius",
        "ready": True,
        "components": {
            "comp-foo": {
                "hit": True,
                "verification_report": verification_report,
                "license_scan": {"blocked": False, "matches": []},
                "secret_scan": {"flagged": False, "findings": []},
            }
        },
        "capabilities": {},
        "not_ready_reasons": [],
    }


def _write_tracker_standin(repo_root):
    report_literal = repr(_verify_report())
    src = (
        "import copy\n"
        "\n"
        "REPORT = " + report_literal + "\n"
        "\n"
        "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
        "    return copy.deepcopy(REPORT)\n"
        "\n"
        "def last_requirement_failures(component_id, repo_root):\n"
        "    return []\n"
    )
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", src)


def _to_plain(value, depth=0):
    if depth > 50:
        return str(value)
    if isinstance(value, dict):
        return {str(k): _to_plain(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_to_plain(v, depth + 1) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            f.name: _to_plain(getattr(value, f.name), depth + 1)
            for f in dataclasses.fields(value)
        }
    if hasattr(value, "__dict__"):
        return {
            str(k): _to_plain(v, depth + 1)
            for k, v in vars(value).items()
            if not str(k).startswith("__")
        }
    return str(value)


def _build_fixture(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _git(repo_root, "symbolic-ref", "HEAD", "refs/heads/main")

    comp_dir = repo_root / "specs" / "components" / "foo"
    _write(comp_dir / "component.md", COMPONENT_MD)
    _write(comp_dir / "requirements" / "R-FOO-001.md",
           _requirement("The foo MUST return a value."))
    _write(comp_dir / "acceptance" / "AC-FOO-001.md", ACCEPTANCE)
    _write(comp_dir / "constraints.md", "# Constraints\n\nNone.\n")
    _write_tracker_standin(repo_root)

    gen_file = repo_root / "gen" / "foo" / "foo.py"
    _write(gen_file, _gen_code("GENCODE_MARKER_OLD_ZQ7X", "zq7x_old_helper", 30))

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "base")

    # Feature branch: spec change plus a substantial rewrite of generated code.
    _git(repo_root, "checkout", "-q", "-b", "feature")
    _write(comp_dir / "requirements" / "R-FOO-001.md",
           _requirement("The foo MUST return a strictly positive value."))
    _write(gen_file, _gen_code("GENCODE_MARKER_NEW_K4VW", "k4vw_new_helper", 45))
    _write(repo_root / "gen" / "foo" / "foo_extra.py",
           _gen_code("GENCODE_MARKER_NEW_K4VW", "k4vw_new_helper_extra", 20))
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "change spec and regenerate foo")

    # Further uncommitted working-tree rewrite of generated code.
    _write(gen_file, _gen_code("GENCODE_MARKER_WT_P9RJ", "p9rj_worktree_helper", 40))

    return repo_root


def test_packet_contains_no_generated_code_diff(tmp_path):
    repo_root = _build_fixture(tmp_path)
    changed_ids = ["comp-foo", "R-FOO-001"]

    old_cwd = os.getcwd()
    try:
        os.chdir(str(repo_root))
        packet = review_packet_builder.build_review_packet(changed_ids, repo_root)
    finally:
        os.chdir(old_cwd)

    assert packet is not None
    # The packet is a real ReviewPacket with its spec_diff section present.
    spec_diff = field(packet, "spec_diff")
    assert spec_diff is None or isinstance(spec_diff, str)

    plain = _to_plain(packet)
    text = json.dumps(plain, default=str, ensure_ascii=False)
    text_all = text + "\n" + str(spec_diff or "")

    for marker in MARKERS:
        assert marker not in text_all, (
            "generated-code content %r leaked into the review packet" % marker
        )

    for path_fragment in ("a/gen/foo/", "b/gen/foo/", "+++ b/gen/", "--- a/gen/"):
        assert path_fragment not in text_all, (
            "generated-code diff header %r found in the review packet" % path_fragment
        )