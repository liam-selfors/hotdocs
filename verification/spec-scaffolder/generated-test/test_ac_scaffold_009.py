# hotdocs-criterion: sha256:f5a22124cc094c160305717232a43de8e5d70ae27fd1191e858a71807e736e8f
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


def test_new_capability_writes_exact_layout_and_refuses_duplicates_and_bad_names(tmp_path):
    repo_root = _make_repo(tmp_path)
    expected_path = repo_root / "specs" / "product" / "order-book.md"

    result = spec_scaffolder.new_capability(
        repo_root, "order-book", owners=["team-a", "team-b"]
    )

    assert Path(result).resolve() == expected_path.resolve()
    assert expected_path.is_file()
    content = expected_path.read_text()
    assert content == EXPECTED_ORDER_BOOK
    lines = content.split("\n")
    assert lines[0] == "---"
    assert lines[2] == "title: Order Book"
    assert content.endswith("## Purpose\n\nTODO.\n")

    with pytest.raises(FileExistsError):
        spec_scaffolder.new_capability(repo_root, "order-book")

    with pytest.raises(ValueError):
        spec_scaffolder.new_capability(repo_root, "Order_Book")

    assert expected_path.read_text() == EXPECTED_ORDER_BOOK
    product_dir = repo_root / "specs" / "product"
    assert sorted(p.name for p in product_dir.iterdir()) == ["order-book.md"]


def test_main_capability_new_success_and_errors(tmp_path, capsys):
    repo_root = _make_repo(tmp_path)
    capsys.readouterr()

    code = spec_scaffolder.main(
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
    assert code == 0
    assert captured.out.splitlines() == ["specs/product/ledger.md", "id: P-LEDGER"]

    ledger = repo_root / "specs" / "product" / "ledger.md"
    assert ledger.is_file()
    ledger_lines = ledger.read_text().splitlines()
    assert "title: The Ledger" in ledger_lines
    assert ledger_lines[2] == "title: The Ledger"
    owners_lines = [line for line in ledger_lines if line.startswith("owners:")]
    assert owners_lines == ["owners: [unassigned]"]
    original = ledger.read_text()

    code = spec_scaffolder.main(
        ["capability", "new", "ledger", "--repo-root=" + str(repo_root)]
    )
    captured = capsys.readouterr()
    assert code == 1
    err_lines = [line for line in captured.err.splitlines() if line.strip()]
    assert len(err_lines) == 1
    assert err_lines[0].startswith("error: ")
    assert ledger.read_text() == original

    code = spec_scaffolder.main(["capability", "new"])
    captured = capsys.readouterr()
    assert code == 2
    err_lines = captured.err.splitlines()
    assert err_lines
    assert err_lines[0].startswith("usage error: ")

    code = spec_scaffolder.main(["capability"])
    captured = capsys.readouterr()
    assert code == 2
    err_lines = captured.err.splitlines()
    assert err_lines
    assert err_lines[0].startswith("usage error: ")