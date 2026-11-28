# hotdocs-criterion: sha256:cc45e95bbb02a837e2a1d69fbde2ae18b928c116d73b96a0a7e858e041d99ea3
from pathlib import Path

import pytest

import spec_scaffolder


EXPECTED_ORDER_BOOK = (
    "---\n"
    "id: P-ORDER-BOOK\n"
    "title: Order Book\n"
    "status: draft\n"
    "owners: [team-a, team-b]\n"
    "---\n"
    "\n"
    "# Order Book\n"
    "\n"
    "## Purpose\n"
    "\n"
    "TODO.\n"
)


def _make_repo(tmp_path):
    repo_root = tmp_path / "repo"
    (repo_root / "specs").mkdir(parents=True)
    return repo_root


def test_new_capability_library(tmp_path):
    repo_root = _make_repo(tmp_path)
    target = repo_root / "specs" / "product" / "order-book.md"

    result = spec_scaffolder.new_capability(
        repo_root, "order-book", owners=["team-a", "team-b"]
    )
    assert Path(result).resolve() == target.resolve()
    assert target.is_file()

    content = target.read_text(encoding="utf-8")
    assert content == EXPECTED_ORDER_BOOK
    lines = content.split("\n")
    assert lines[0] == "---"
    assert lines[2] == "title: Order Book"
    assert content.endswith("## Purpose\n\nTODO.\n")

    original_bytes = target.read_bytes()

    with pytest.raises(FileExistsError):
        spec_scaffolder.new_capability(repo_root, "order-book")
    assert target.read_bytes() == original_bytes

    with pytest.raises(ValueError):
        spec_scaffolder.new_capability(repo_root, "Order_Book")
    assert target.read_bytes() == original_bytes

    product = repo_root / "specs" / "product"
    entries = sorted(p.name for p in product.iterdir())
    assert entries == ["order-book.md"]


def test_new_capability_cli(tmp_path, capsys, monkeypatch):
    repo_root = _make_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    rc = spec_scaffolder.main(
        [
            "capability",
            "new",
            "ledger",
            "--title",
            "The Ledger",
            "--repo-root=" + str(repo_root),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.splitlines() == ["specs/product/ledger.md", "id: P-LEDGER"]
    assert captured.out.replace("\r\n", "\n") == "specs/product/ledger.md\nid: P-LEDGER\n"

    target = repo_root / "specs" / "product" / "ledger.md"
    assert target.is_file()
    file_lines = target.read_text(encoding="utf-8").splitlines()
    assert file_lines[2] == "title: The Ledger"
    assert file_lines[4] == "owners: [unassigned]"
    original_bytes = target.read_bytes()

    rc = spec_scaffolder.main(
        ["capability", "new", "ledger", "--repo-root=" + str(repo_root)]
    )
    captured = capsys.readouterr()
    assert rc == 1
    err_lines = captured.err.splitlines()
    assert len(err_lines) == 1
    assert err_lines[0].startswith("error: ")
    assert target.read_bytes() == original_bytes

    rc = spec_scaffolder.main(["capability", "new"])
    captured = capsys.readouterr()
    assert rc == 2
    err_lines = captured.err.splitlines()
    assert err_lines
    assert err_lines[0].startswith("usage error: ")

    rc = spec_scaffolder.main(["capability"])
    captured = capsys.readouterr()
    assert rc == 2
    err_lines = captured.err.splitlines()
    assert err_lines
    assert err_lines[0].startswith("usage error: ")