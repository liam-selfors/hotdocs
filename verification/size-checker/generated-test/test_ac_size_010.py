# hotdocs-criterion: sha256:9b122c9ddbb18c730b1f5ca37d35592538c65ab429d185af493a585dc00beb17
import shutil
from pathlib import Path

import size_checker


def field(value, name):
    return value[name] if isinstance(value, dict) else getattr(value, name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_comp_p(repo_root):
    comp = repo_root / "specs" / "components" / "p"
    write(
        comp / "component.md",
        "---\n"
        "id: comp-p\n"
        "title: P\n"
        "status: draft\n"
        "owners: [team-a]\n"
        "depends_on: []\n"
        "sealed: true\n"
        "source_path: legacy/p/\n"
        "---\n"
        "\n"
        "# P\n"
        "\n"
        "## Purpose\n"
        "\n"
        "A small fixture component.\n",
    )
    # 21 requirements: one above the requirement_count warn threshold of 20.
    for i in range(1, 22):
        rid = "R-P-" + str(i).zfill(3)
        aid = "AC-P-" + str(i).zfill(3)
        write(
            comp / "requirements" / (rid + ".md"),
            "# " + rid + "\n\n**" + rid + "** — The thing MUST work.\n",
        )
        write(
            comp / "acceptance" / (aid + ".md"),
            "# " + aid + "\n\nCovers: " + rid + "\nKind: generated-test\n\n"
            "Given a thing, when it runs, then it works.\n",
        )


def build_ghost(repo_root):
    ghost = repo_root / "specs" / "components" / "ghost"
    write(
        ghost / "requirements" / "R-GHOST-001.md",
        "\n".join(["# R-GHOST-001", "", "**R-GHOST-001** — x."]) + "\n",
    )


def normalize(findings):
    out = []
    for f in findings:
        out.append(
            (
                field(f, "rule_id"),
                field(f, "severity"),
                field(f, "file"),
                field(f, "line"),
                field(f, "message"),
            )
        )
    return out


def test_ac_size_010_component_without_root_is_skipped(tmp_path):
    with_ghost = tmp_path / "with_ghost"
    without_ghost = tmp_path / "without_ghost"
    with_ghost.mkdir()
    without_ghost.mkdir()

    build_comp_p(with_ghost)
    build_ghost(with_ghost)
    build_comp_p(without_ghost)
    build_ghost(without_ghost)
    shutil.rmtree(without_ghost / "specs" / "components" / "ghost")
    assert not (without_ghost / "specs" / "components" / "ghost").exists()

    # Must return without raising.
    findings_with = normalize(size_checker.check(with_ghost))
    findings_without = normalize(size_checker.check(without_ghost))

    # Sanity: comp-p's requirement_count exceeds its warn threshold.
    assert any(
        rule == "R-SIZE-001" and "requirement_count" in msg and msg.startswith("p: ")
        for rule, _sev, _file, _line, msg in findings_without
    ), findings_without

    assert findings_with == findings_without

    for rule, sev, file, line, msg in findings_with:
        assert "ghost" not in str(msg), msg
        assert "ghost" not in str(file), file