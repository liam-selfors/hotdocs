# hotdocs-criterion: sha256:72d512f0be4cae77d553cbcdf938fafd50d7be0ab3d2e2968b65ef1245146239
import json
import re
import subprocess
from pathlib import Path

import review_packet_builder


ADDED_SPEC_LINE = "The widget MUST emit a frobnication receipt (fixture-line-7f3a)."
LICENSE_PACKAGE = "evilpkg-gpl"
LICENSE_FILE = "gen/foo/vendor/evilpkg_gpl.py"
SECRET_FILE = "a/b.py"
CAPABILITY_ID = "P-FOO-EDIT"


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _git(repo_root, *args):
    subprocess.run(
        [
            "git",
            "-c", "user.name=hotdocs-test",
            "-c", "user.email=hotdocs-test@example.invalid",
            "-c", "commit.gpgsign=false",
            *args,
        ],
        cwd=str(repo_root),
        check=True,
        capture_output=True,
        text=True,
    )


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _component_md(slug, extra_lines):
    text = "---\n"
    text += "id: comp-" + slug + "\n"
    text += "title: " + slug.capitalize() + " component\n"
    text += "status: draft\n"
    text += "owners: [pipeline-team]\n"
    text += "depends_on: []\n"
    for line in extra_lines:
        text += line + "\n"
    text += "---\n\n# " + slug.capitalize() + "\n\nFixture component.\n"
    return text


def _write_component(repo_root, slug, upper, extra_lines):
    base = repo_root / "specs" / "components" / slug
    _write(base / "component.md", _component_md(slug, extra_lines))
    req_id = "R-" + upper + "-001"
    ac_id = "AC-" + upper + "-001"
    _write(
        base / "requirements" / (req_id + ".md"),
        "# " + req_id + "\n\n**" + req_id + "** — The " + slug + " component MUST work.\n",
    )
    _write(
        base / "acceptance" / (ac_id + ".md"),
        "# " + ac_id + "\n\nCovers: " + req_id + "\nKind: llm-judge\n\nIt works.\n",
    )


def _verification_report(mutation_score):
    return {
        "component_id": "comp-foo",
        "criteria": [
            {"id": "AC-FOO-001", "covers": "R-FOO-001", "kind": "compiled", "result": "pass"},
        ],
        "requirement_results": {"R-FOO-001": "pass"},
        "interface_drift": False,
        "mutation_score": mutation_score,
        "mutation_error": None,
        "assets": [
            {
                "kind": "python",
                "path": ".",
                "definition_sha256": None,
                "adapter_sha256": "sha256:" + "0" * 64,
                "versions": {"python": "3.12.4"},
                "lockfile_sha256": None,
            }
        ],
        "drivers": [],
        "overall": "pass",
    }


def _license_scan(flagged):
    if flagged:
        return {
            "blocked": True,
            "gate_version": "license_scanner@1.0.0",
            "flagged": [
                {"package": LICENSE_PACKAGE, "license": "GPL-3.0-only", "file": LICENSE_FILE}
            ],
            "cache_hit": False,
        }
    return {
        "blocked": False,
        "gate_version": "license_scanner@1.0.0",
        "flagged": [],
        "cache_hit": False,
    }


def _secret_scan(flagged):
    matches = []
    if flagged:
        matches = [{"rule_id": "AWS Access Key", "risk_tier": "high", "file": SECRET_FILE, "line": 3}]
    return {
        "scope": "full",
        "gate_version": "secret_scanner@3.1.0+detect-secrets.1.5.0",
        "flagged": bool(matches),
        "matches": matches,
        "allowed": [],
        "unused_allowlist_entries": [],
        "notified": False,
        "notification_delivery_error": None,
        "cache_hit": False,
    }


def _verify_report(with_flags):
    capabilities = {}
    if with_flags:
        capabilities = {
            CAPABILITY_ID: {
                "hit": True,
                "capability_scenario_report": {
                    CAPABILITY_ID: {"overall": "pass", "scenarios": []}
                },
            }
        }
    return {
        "scope": "blast-radius",
        "ready": not with_flags,
        "components": {
            "comp-foo": {
                "hit": True,
                "reason": None,
                "verification_report": _verification_report(0.92 if with_flags else 1.0),
                "license_scan": _license_scan(with_flags),
                "secret_scan": _secret_scan(False),
            }
        },
        "capabilities": capabilities,
        "secret_scan": _secret_scan(with_flags),
        "not_ready_reasons": (
            ["repository secret scan flagged"] if with_flags else []
        ),
    }


def _write_fake_tracker(repo_root, report, log_path):
    src = ""
    src += "import copy\n"
    src += "\n"
    src += "REPORT = " + repr(report) + "\n"
    src += "LOG_PATH = " + repr(str(log_path)) + "\n"
    src += "\n"
    src += "\n"
    src += "def check_readiness(repo_root, changed_ids=None, model=None, seed=0, llm_backend=None):\n"
    src += "    with open(LOG_PATH, 'a', encoding='utf-8') as fh:\n"
    src += "        fh.write('check_readiness ' + repr(changed_ids) + '\\n')\n"
    src += "    result = copy.deepcopy(REPORT)\n"
    src += "    result['scope'] = 'blast-radius' if changed_ids is not None else 'whole-corpus'\n"
    src += "    return result\n"
    src += "\n"
    src += "\n"
    src += "def last_requirement_failures(component_id, repo_root):\n"
    src += "    return []\n"
    _write(repo_root / "gen" / "provenance-tracker" / "provenance_tracker.py", src)


def _build_repo(repo_root, with_flags):
    repo_root.mkdir(parents=True, exist_ok=True)
    _git(repo_root, "init", "-q")
    _git(repo_root, "symbolic-ref", "HEAD", "refs/heads/main")

    foo_extra = []
    if with_flags:
        foo_extra.append("realizes: [" + CAPABILITY_ID + "]")
        cap_doc = "---\n"
        cap_doc += "id: " + CAPABILITY_ID + "\n"
        cap_doc += "title: Foo edit capability\n"
        cap_doc += "status: draft\n"
        cap_doc += "owners: [pipeline-team]\n"
        cap_doc += "---\n\n# " + CAPABILITY_ID + "\n\nFixture capability.\n"
        _write(repo_root / "specs" / "capabilities" / (CAPABILITY_ID + ".md"), cap_doc)
        record = {
            "capability_id": CAPABILITY_ID,
            "gate_version": "capability_scenario_verifier@3.0.0",
            "content_hash": "sha256:" + "1" * 64,
            "realizing_components": ["comp-foo"],
            "capability_scenario_report": {CAPABILITY_ID: {"overall": "pass", "scenarios": []}},
            "model": "claude-sonnet-5",
            "seed": 0,
        }
        _write(
            repo_root / "verification" / "capabilities" / CAPABILITY_ID / ".provenance.json",
            json.dumps(record, indent=2, sort_keys=True) + "\n",
        )
    _write_component(repo_root, "foo", "FOO", foo_extra)
    _write_component(repo_root, "bar", "BAR", ["sealed: false"])
    _write_component(repo_root, "baz", "BAZ", ["sealed: true", "source_path: legacy/baz/"])
    _write(repo_root / "gen" / "foo" / "foo.py", "VALUE = 1\n")
    _write(repo_root / "gen" / "baz" / "baz.py", "VALUE = 2\n")
    _write(repo_root / "README.md", "fixture\n")

    log_path = repo_root.parent / (repo_root.name + "-tracker.log")
    _write_fake_tracker(repo_root, _verify_report(with_flags), log_path)

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "base")
    _git(repo_root, "update-ref", "refs/remotes/origin/main", "HEAD")

    if with_flags:
        _git(repo_root, "checkout", "-q", "-b", "feature")
        # Real sealed: false -> sealed: true transition.
        _write(
            repo_root / "specs" / "components" / "bar" / "component.md",
            _component_md("bar", ["sealed: true", "source_path: legacy/bar/"]),
        )
        # Real pinned-override addition.
        _write(
            repo_root / "gen" / "baz" / ".overrides.json",
            json.dumps({"files": ["baz.py"]}, indent=2, sort_keys=True) + "\n",
        )
        # A line this PR adds to a spec file.
        req = repo_root / "specs" / "components" / "foo" / "requirements" / "R-FOO-001.md"
        req.write_text(req.read_text(encoding="utf-8") + "\n" + ADDED_SPEC_LINE + "\n", encoding="utf-8")
        _git(repo_root, "add", "-A")
        _git(repo_root, "commit", "-q", "-m", "change")

    return log_path


def _headings(markdown):
    lines = markdown.splitlines()
    result = []
    in_fence = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if m:
            result.append((idx, len(m.group(1)), m.group(2)))
    return lines, result


def _section(markdown, keyword):
    lines, heads = _headings(markdown)
    for pos, (idx, level, text) in enumerate(heads):
        if keyword in text.lower():
            end = len(lines)
            for idx2, level2, _ in heads[pos + 1:]:
                if level2 <= level:
                    end = idx2
                    break
            return "\n".join(lines[idx + 1:end])
    raise AssertionError(
        "no section heading containing " + repr(keyword) + " in markdown:\n" + markdown
    )


def _label_segment(section, label, other_labels):
    start = section.find(label)
    assert start != -1, "missing label " + repr(label) + " in section:\n" + section
    body_start = start + len(label)
    end = len(section)
    for other in other_labels:
        pos = section.find(other, body_start)
        if pos != -1 and pos < end:
            end = pos
    return section[body_start:end]


def _run(repo_root, capsys):
    capsys.readouterr()
    code = review_packet_builder.main(
        ["review-packet", "build", "--changed=R-FOO-001", "--repo-root=" + str(repo_root)]
    )
    out = capsys.readouterr()
    return code, out.out, out.err


def test_markdown_renders_real_detail_for_every_section(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    log_path = _build_repo(repo_root, with_flags=True)

    code, md, err = _run(repo_root, capsys)
    assert code == 0, "stdout:\n" + md + "\nstderr:\n" + err
    assert log_path.is_file() and "check_readiness" in log_path.read_text(encoding="utf-8")

    license_section = _section(md, "license scan")
    assert LICENSE_PACKAGE in license_section, license_section

    secret_section = _section(md, "secret scan")
    assert SECRET_FILE in secret_section, secret_section

    residual_section = _section(md, "residual")
    assert "comp-foo" in residual_section, residual_section
    assert "0.92" in residual_section, residual_section

    capability_section = _section(md, "capability scenario")
    assert CAPABILITY_ID in capability_section, capability_section

    exemption_section = _section(md, "exemption")
    sealed_part = _label_segment(exemption_section, "**Sealed:**", ["**Pinned Overrides:**"])
    pinned_part = _label_segment(exemption_section, "**Pinned Overrides:**", ["**Sealed:**"])
    assert "comp-bar" in sealed_part, exemption_section
    assert "comp-baz" in pinned_part, exemption_section

    diff_section = _section(md, "diff")
    assert ADDED_SPEC_LINE in diff_section, diff_section

    changed_section = _section(md, "requirement")
    assert "R-FOO-001" in changed_section, changed_section

    regenerated_section = _section(md, "regenerat")
    assert "comp-foo" in regenerated_section, regenerated_section

    verification_section = _section(md, "verification result")
    assert "comp-foo" in verification_section, verification_section

    hit_section = _section(md, "provenance hit")
    hit_lines = [line.strip() for line in hit_section.splitlines()]
    assert "- comp-foo: hit=true" in hit_lines, hit_section


def test_markdown_renders_clean_placeholders_when_nothing_flagged(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    log_path = _build_repo(repo_root, with_flags=False)

    code, md, err = _run(repo_root, capsys)
    assert code == 0, "stdout:\n" + md + "\nstderr:\n" + err
    assert log_path.is_file() and "check_readiness" in log_path.read_text(encoding="utf-8")

    for keyword in ("license scan", "secret scan", "capability scenario"):
        section = _section(md, keyword)
        assert section.strip() != "", (
            "section " + repr(keyword) + " has no placeholder:\n" + md
        )
        assert LICENSE_PACKAGE not in section, section
        assert SECRET_FILE not in section, section
        assert CAPABILITY_ID not in section, section

    verification_section = _section(md, "verification result")
    entry_lines = [
        line.strip()
        for line in verification_section.splitlines()
        if line.strip().startswith("- comp-foo:")
    ]
    assert entry_lines, verification_section
    assert any(line[len("- comp-foo:"):].strip() for line in entry_lines), verification_section