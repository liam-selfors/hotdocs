# hotdocs-criterion: sha256:a97fccfe0d68a73e869a0a13418e053c33817fc903c4ec980bcb9a6b57d5e9b4
"""AC-LINT-013: a secret var declaration carrying a default field fails R-LINT-013."""

from pathlib import Path

import spec_linter


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _var_doc(var_id, title, sensitivity, extra_bullets):
    lines = [
        "---",
        "id: " + var_id,
        "title: " + title,
        "status: draft",
        "owners: [pipeline-team]",
        "---",
        "",
        "# " + title,
        "",
        "- name: " + var_id,
        "- required",
        "- type: string",
        "- description: A test configuration parameter.",
        "- sensitivity: " + sensitivity,
    ]
    lines.extend(extra_bullets)
    lines.append("")
    return "\n".join(lines)


def _build_corpus(repo_root):
    specs = repo_root / "specs"
    _write(
        specs / "glossary.md",
        "# Glossary\n\n- **Widget** — a test term.\n",
    )
    _write(
        specs / "vars" / "VAR-API-TOKEN.md",
        _var_doc(
            "VAR-API-TOKEN",
            "API Token",
            "secret",
            ["- default: hunter2"],
        ),
    )
    _write(
        specs / "vars" / "VAR-SAFE-SECRET.md",
        _var_doc("VAR-SAFE-SECRET", "Safe Secret", "secret", []),
    )
    _write(
        specs / "vars" / "VAR-PLAIN-URL.md",
        _var_doc(
            "VAR-PLAIN-URL",
            "Plain URL",
            "non-secret",
            ["- default: https://example.invalid/"],
        ),
    )


def _lint013(report):
    findings = field(report, "findings")
    return [f for f in findings if field(f, "rule_id") == "R-LINT-013"]


def _norm(p):
    return str(p).replace("\\", "/")


def test_secret_var_with_default_fails_r_lint_013(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    report = spec_linter.lint(None, repo_root)

    hits = _lint013(report)
    offending = [
        f for f in hits if _norm(field(f, "file")).endswith("specs/vars/VAR-API-TOKEN.md")
    ]
    assert offending, "expected an R-LINT-013 finding on VAR-API-TOKEN.md, got: " + repr(hits)
    assert all(field(f, "severity") == "fail" for f in offending)
    assert field(report, "hard_failures") >= 1

    # Controls: a secret var without default/example, and a non-secret var
    # with a default, must not be flagged by R-LINT-013.
    for f in hits:
        name = _norm(field(f, "file"))
        assert not name.endswith("specs/vars/VAR-SAFE-SECRET.md"), repr(f)
        assert not name.endswith("specs/vars/VAR-PLAIN-URL.md"), repr(f)


def test_secret_var_with_default_fails_when_linted_by_path(tmp_path):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    target = repo_root / "specs" / "vars" / "VAR-API-TOKEN.md"
    report = spec_linter.lint([target], repo_root)

    hits = [
        f
        for f in _lint013(report)
        if _norm(field(f, "file")).endswith("specs/vars/VAR-API-TOKEN.md")
    ]
    assert hits, "expected an R-LINT-013 finding when linting the file directly"
    assert all(field(f, "severity") == "fail" for f in hits)


def test_cli_exits_1_for_secret_var_with_default(tmp_path, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _build_corpus(repo_root)

    code = spec_linter.main(["--format=json", "--repo-root=" + str(repo_root)])
    out = capsys.readouterr().out

    assert code == 1
    assert "R-LINT-013" in out