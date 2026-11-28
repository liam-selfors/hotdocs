# hotdocs-criterion: sha256:e7848e6c6c3f04c0a6c8894eea2d34842d58adcbf10734ee46e86ad6ad48f13b
import test_author


def _plant_assembler(repo_root):
    target_dir = repo_root / "gen" / "spec-bundle-assembler"
    target_dir.mkdir(parents=True, exist_ok=True)
    message = "unknown component id: comp-a"
    source = (
        "def assemble_criterion(component_id, criterion_id, repo_root):\n"
        "    raise Exception(" + repr(message) + ")\n"
        "\n"
        "\n"
        "def assemble(component_id, repo_root, mode=" + repr("cold") + "):\n"
        "    raise Exception(" + repr(message) + ")\n"
    )
    (target_dir / "spec_bundle_assembler.py").write_text(source, encoding="utf-8")


def test_main_reports_bundle_failure_without_calling_author_test(tmp_path, monkeypatch, capsys):
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.chdir(repo_root)
    _plant_assembler(repo_root)

    log_path = tmp_path / "author_test_calls.log"

    def stub(*args, **kwargs):
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write("called\n")
        raise AssertionError("author_test must not be called")

    monkeypatch.setattr(test_author, "author_test", stub)

    code = test_author.main(
        ["comp-a", "AC-A-001", "--model=m", "--repo-root=" + str(repo_root)]
    )

    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == ""
    assert captured.err == "AC-A-001: cannot build its bundle: unknown component id: comp-a\n"
    assert not log_path.exists()

    verification = repo_root / "verification"
    assert not verification.exists() or not any(p.is_file() for p in verification.rglob("*"))